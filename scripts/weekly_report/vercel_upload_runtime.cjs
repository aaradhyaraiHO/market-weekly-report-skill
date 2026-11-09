// Process-local upload transport. Never logs headers, bodies or query strings.
const {registerHooks, createRequire, isBuiltin} = require('node:module');
const {pathToFileURL} = require('node:url');
const https = require('node:https');
const path = require('node:path');
const vendor = process.env.WEEKLY_VERCEL_VENDOR_ROOT;
const isolated = process.env.WEEKLY_VERCEL_ISOLATED_ROOT;
if (!path.isAbsolute(vendor || '') || !path.isAbsolute(isolated || '')) {
  throw new Error('Verified Vercel tool paths are required');
}
const vendorRequire = createRequire(path.join(vendor, 'package.json'));
const isolatedURL = pathToFileURL(isolated + path.sep).href;
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL?.startsWith(isolatedURL) && !isBuiltin(specifier) &&
        !specifier.startsWith('.') && !specifier.startsWith('/') &&
        !specifier.startsWith('#') && !specifier.includes(':')) {
      return {url: pathToFileURL(vendorRequire.resolve(specifier)).href, shortCircuit: true};
    }
    return nextResolve(specifier, context);
  }
});

const originalRequest = https.request;
const uploadAgent = new https.Agent({keepAlive: false, maxSockets: 1});
const agents = new WeakMap();
function freshUploadAgent(previous) {
  if (previous === false) return false;
  if (!previous) return uploadAgent;
  // Preserve proxy/custom connection routing and all existing TLS options.
  if (Object.getPrototypeOf(previous) !== https.Agent.prototype ||
      previous.createConnection !== https.Agent.prototype.createConnection) return previous;
  if (!agents.has(previous)) {
    agents.set(previous, new https.Agent({...previous.options, keepAlive: false, maxSockets: 1}));
  }
  return agents.get(previous);
}
https.request = function (...args) {
  let host, pathname, optionIndex;
  if (typeof args[0] === 'string' || args[0] instanceof URL) {
    const url = new URL(args[0]);
    host = url.hostname;
    pathname = url.pathname;
    optionIndex = 1;
  } else if (args[0] && typeof args[0] === 'object') {
    host = args[0].hostname || args[0].host;
    pathname = String(args[0].path || '').split('?')[0];
    optionIndex = 0;
  }
  if (host !== 'api.vercel.com' || pathname !== '/v2/files') {
    return originalRequest.apply(this, args);
  }
  if (optionIndex === 1 && (typeof args[1] === 'function' || args[1] === undefined)) {
    args.splice(1, 0, {agent: uploadAgent});
  } else {
    args[optionIndex] = {...args[optionIndex], agent: freshUploadAgent(args[optionIndex]?.agent)};
  }
  const started = Date.now();
  const request = originalRequest.apply(this, args);
  request.once('response', response => {
    console.error(`[upload-transport] /v2/files HTTP ${response.statusCode}; ${Date.now() - started}ms`);
  });
  request.once('error', error => {
    console.error(`[upload-transport] /v2/files error ${error.code || 'UNKNOWN'}; ${Date.now() - started}ms`);
  });
  return request;
};
