const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { updateDownload } = require('./update-download.cjs');
const repository = 'com-in/SCS-Saves-Editor';
const url = `https://github.com/${repository}/releases/download/v1.3.0/SCS.exe`;
const release = { assets: [{ name: 'SCS.exe', state: 'uploaded', browser_download_url: url }] };

test('updates actual homepage to uploaded versioned EXE and is idempotent', () => {
  const html = fs.readFileSync('docs/index.html', 'utf8');
  const result = updateDownload(html, release, repository);
  assert.ok(result.includes(`href="https://gh-proxy.org/${url}"`));
  assert.ok(result.includes(`href="https://github.com/${repository}/releases"`));
  assert.equal(updateDownload(result, release, repository), result);
});

test('rejects absent, incomplete and foreign assets', () => {
  for (const assets of [[], [{ ...release.assets[0], name: 'Other.exe' }], [{ ...release.assets[0], state: 'new' }],
    [{ ...release.assets[0], browser_download_url: 'https://example.com/mod.exe' }]]) {
    assert.throws(() => updateDownload('', { assets }, repository));
  }
});

test('fails instead of committing when button is missing or duplicated', () => {
  assert.throws(() => updateDownload('<html></html>', release, repository));
  const button = '<a id="accelerated-download" href="old">下载</a>';
  assert.throws(() => updateDownload(button + button, release, repository));
});
