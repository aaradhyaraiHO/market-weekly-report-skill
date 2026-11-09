"""Exercise the actual adapted vendor upload function without network/credentials."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import vercel_upload as upload


class VendorUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.node, cls.vendor = upload.toolchain()
        except (ValueError, FileNotFoundError) as error:
            raise unittest.SkipTest(f'Reviewed local Vercel/Node toolchain not installed: {error}')
        cls.source = (cls.vendor / upload.UPLOAD_FILE).read_text()
        cls.adapted = upload.patched_upload(cls.source)

    def test_adapter_is_byte_identical_to_successful_live_recovery(self):
        self.assertEqual(upload.sha(self.adapted.encode()), upload.ADAPTED_SHA256)
        self.assertEqual(upload.sha((self.vendor / upload.UPLOAD_FILE).read_bytes()), upload.UPLOAD_SHA256)

    def test_isolated_cache_preserves_global_vendor_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory).resolve()
            isolated = upload.prepare_cli(self.vendor, cache)
            self.assertEqual(upload.sha((isolated / upload.UPLOAD_FILE).read_bytes()), upload.ADAPTED_SHA256)
            self.assertEqual(upload.prepare_cli(self.vendor, cache), isolated)
            (isolated / upload.UPLOAD_FILE).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'cache changed'):
                upload.prepare_cli(self.vendor, cache)
        self.assertEqual(upload.sha((self.vendor / upload.UPLOAD_FILE).read_bytes()), upload.UPLOAD_SHA256)

    def test_real_upload_function_retries_faults_preserves_bytes_and_stops_on_auth(self):
        harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const source = JSON.parse(require('node:fs').readFileSync(0, 'utf8')).source;
const networkStart = source.indexOf('var isClientNetworkError =');
const networkEnd = source.indexOf('async function* upload(', networkStart);
const uploadStart = source.indexOf('async function* uploadFiles(options)');
const uploadEnd = source.indexOf('var UploadProgress =', uploadStart);
assert(networkStart > 0 && networkEnd > networkStart && uploadStart > 0 && uploadEnd > uploadStart);
const code = source.slice(networkStart, networkEnd) + source.slice(uploadStart, uploadEnd) + '\n({uploadFiles,isClientNetworkError})';
async function scenario(outcomes) {
  let attempts = 0;
  const payload = Buffer.from('preserve these exact bytes\0\u00e9');
  const policy = [];
  const sandbox = {
    AbortController,
    import_utils4: {
      API_FILES: '/v2/files', createDebug: () => () => {},
      fetchApi: async (endpoint, token, request) => {
        assert.equal(endpoint, '/v2/files');
        assert.equal(token, 'dummy-not-a-secret');
        assert(Buffer.isBuffer(request.body), 'custom Readable must not be used');
        assert(request.body.equals(payload), 'retry changed bytes');
        assert.equal(request.headers['Content-Length'], payload.length);
        const outcome = outcomes[Math.min(attempts++, outcomes.length - 1)];
        if (outcome === 'EPIPE') throw new Error('write EPIPE');
        return {status:outcome, text:async ()=>'Internal Server Error', json:async () => {
          assert(outcome < 500, '5xx body must not be assumed to be JSON');
          return {error:{message:'Forbidden'}};
        }};
      }
    },
    import_async_retry: {default: async (fn, options) => {
      policy.push(options);
      for (let n=0;;n++) {
        let bailed = false;
        try { return await fn(error=>{bailed=true;throw error;}); }
        catch (error) { if(bailed || n >= options.retries) throw error; }
      }
    }},
    import_async_sema: {Sema: class {constructor(n){assert.equal(n,2);}async acquire(){}release(){}}},
    import_https: {default:{Agent:class {}}}, import_http:{default:{Agent:class {}}},
    import_errors3:{DeploymentError:class extends Error {constructor(error){super(error.message);}}}
  };
  const {uploadFiles,isClientNetworkError} = vm.runInNewContext(code, sandbox);
  assert(isClientNetworkError(new Error('write EPIPE')));
  assert(isClientNetworkError(new Error('VERCEL_UPLOAD_5XX: 500')));
  assert(!isClientNetworkError(new Error('HTTP 403 Forbidden')));
  const progress = {bytesUploaded:0,emit(){}};
  const events=[];
  for await (const event of uploadFiles({apiUrl:'https://api.vercel.com',token:'dummy-not-a-secret',
      files:new Map([['sha',{data:payload,names:['fixture']}]]), shas:['sha'], uploads:[progress]}))events.push(event);
  assert(policy.every(x=>x.retries===3 && x.factor===2 && x.minTimeout===1000 && x.maxTimeout===5000));
  return {attempts,events,uploaded:progress.bytesUploaded,bytes:payload.length};
}
(async()=>{
  const recovered=await scenario(['EPIPE',500,200]);
  assert.equal(recovered.attempts,3);assert.equal(recovered.events[0].type,'file-uploaded');
  assert.equal(recovered.uploaded,recovered.bytes);
  const forbidden=await scenario([403]);assert.equal(forbidden.attempts,1);assert.equal(forbidden.events[0].type,'error');
  const exhausted=await scenario(['EPIPE']);assert.equal(exhausted.attempts,4);assert.equal(exhausted.events[0].type,'error');
  console.log('EPIPE/5xx recovered; bytes identical; auth not retried; exhaustion bounded');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run([str(self.node), '-e', harness], input=json.dumps({'source': self.adapted}),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('bytes identical', result.stdout)

    def test_https_override_is_upload_only_and_never_logs_secrets(self):
        harness = r'''
const assert=require('node:assert/strict');
const https=require('node:https');
const {EventEmitter}=require('node:events');
const calls=[];
https.request=(...args)=>{calls.push(args);return new EventEmitter();};
require(process.argv[1]);
const auth='DUMMY_TOKEN_DO_NOT_LOG';
const plain={hostname:'api.vercel.com',path:'/v13/deployments',headers:{Authorization:auth}};
https.request(plain);assert.strictEqual(calls[0][0],plain);
const outside={hostname:'outside.example',path:'/v2/files'};
https.request(outside);assert.strictEqual(calls[1][0],outside);
const request=https.request({hostname:'api.vercel.com',path:'/v2/files?private=DO_NOT_LOG',headers:{Authorization:auth}});
const adjusted=calls[2][0];
assert.equal(adjusted.headers.Authorization,auth);
assert.equal(adjusted.agent.maxSockets,1);
assert.notEqual(adjusted.agent.options.rejectUnauthorized,false);
const customTLS=new https.Agent({ca:'DUMMY_CA',rejectUnauthorized:true});
https.request({hostname:'api.vercel.com',path:'/v2/files',agent:customTLS});
assert.equal(calls[3][0].agent.options.ca,'DUMMY_CA');
assert.equal(calls[3][0].agent.options.rejectUnauthorized,true);
class ProxyAgent extends https.Agent {}
const proxy=new ProxyAgent();
https.request({hostname:'api.vercel.com',path:'/v2/files',agent:proxy});
assert.strictEqual(calls[4][0].agent,proxy);
request.emit('response',{statusCode:200});
const error=new Error('DO_NOT_LOG');error.code='EPIPE';request.emit('error',error);
console.log('scoped HTTPS adjustment passed');
'''
        with tempfile.TemporaryDirectory() as directory:
            import os
            env = dict(os.environ, WEEKLY_VERCEL_VENDOR_ROOT=str(self.vendor),
                       WEEKLY_VERCEL_ISOLATED_ROOT=str(Path(directory).resolve()))
            result = subprocess.run([str(self.node), '-e', harness, str(upload.RUNTIME)], env=env,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('DO_NOT_LOG', result.stderr)
        self.assertIn('HTTP 200', result.stderr)
        self.assertIn('error EPIPE', result.stderr)


if __name__ == '__main__':
    unittest.main()
