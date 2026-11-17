// Content-addressed metadata only; retain bytes for at most active missing files.
// These entries satisfy the pinned CLI's prepareFiles/progress interfaces.
const fs = require('node:fs');
const crypto = require('node:crypto');
async function hashes(files, map = new Map()) {
  for (const name of files) {
    const stat = await fs.promises.lstat(name);
    if (stat.isSymbolicLink()) throw new Error('Symlink in prepared upload');
    let sha;
    if (stat.isFile()) {
      const digest = crypto.createHash('sha1');
      for await (const chunk of fs.createReadStream(name)) digest.update(chunk);
      sha = digest.digest('hex');
    } else if (!stat.isDirectory()) throw new Error('Unsupported prepared upload file');
    const existing = map.get(sha);
    if (existing) existing.names = [...new Set([...existing.names, name])];
    else map.set(sha, {names:[name], data: stat.isFile() ? {length:stat.size, byteLength:stat.size} : undefined,
                       mode:stat.mode, reportDisk:stat.isFile()});
  }
  return map;
}
async function load(file, sha) {
  if (!file.reportDisk) return file.data;
  const handle = await fs.promises.open(file.names[0], fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const stat = await handle.stat();
    if (!stat.isFile()) throw new Error('Prepared upload file type changed');
    const data = await handle.readFile();
    if (data.length !== file.data.length || crypto.createHash('sha1').update(data).digest('hex') !== sha)
      throw new Error('Prepared upload bytes changed');
    return data;
  } finally { await handle.close(); }
}
module.exports = {hashes, load};
