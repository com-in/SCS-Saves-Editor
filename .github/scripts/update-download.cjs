function updateDownload(html, release, repository) {
  const expectedPrefix = `https://github.com/${repository}/releases/download/`;
  const assets = (release.assets || []).filter(asset =>
    asset.state === 'uploaded' && asset.name.toLowerCase().endsWith('.exe') &&
    asset.browser_download_url?.startsWith(expectedPrefix));
  const asset = assets.find(asset => asset.name === 'SCS.exe');
  if (!asset) throw new Error('Release 缺少已上传的 SCS.exe。');
  const escapeAttribute = value => value.replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const pattern = /(<a\b[^>]*\bid="accelerated-download"[^>]*\bhref=")[^"]*(")/g;
  let count = 0;
  const result = html.replace(pattern, (_, before, after) => {
    count += 1;
    return before + escapeAttribute('https://gh-proxy.org/' + asset.browser_download_url) + after;
  });
  if (count !== 1) throw new Error(`应找到一个加速下载按钮，实际找到 ${count} 个。`);
  return result;
}

module.exports = { updateDownload };
