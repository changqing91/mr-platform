'use strict';

const os = require('os');
const fs = require('fs');
const { execSync } = require('child_process');
const crypto = require('crypto');

/**
 * 采集当前服务器的硬件指纹。
 * 算法与 tools/license-gen/fingerprint.js 保持完全一致。
 *
 * 稳定标识符策略（按优先级）：
 *   Linux  : /etc/machine-id（系统安装时生成，永不变）
 *   macOS  : ioreg IOPlatformSerialNumber（硬件序列号）
 *   fallback: hostname + CPU 型号
 */
function getStableId() {
  const platform = os.platform();
  if (platform === 'linux') {
    try {
      return fs.readFileSync('/etc/machine-id', 'utf8').trim();
    } catch (_) {}
    try {
      return fs.readFileSync('/var/lib/dbus/machine-id', 'utf8').trim();
    } catch (_) {}
  } else if (platform === 'darwin') {
    try {
      const out = execSync(
        'ioreg -rd1 -c IOPlatformExpertDevice | awk \'/IOPlatformSerialNumber/ { split($0,a,"\\""); print a[4] }\'',
        { timeout: 3000 }
      ).toString().trim();
      if (out) return out;
    } catch (_) {}
  }
  // fallback
  return null;
}

function getMachineId() {
  const stableId = getStableId();
  const hostname = os.hostname();
  const cpuModel = (os.cpus()[0] && os.cpus()[0].model) || 'unknown';

  console.log('Detected stable ID:', stableId || '(none, using fallback)');
  console.log('Detected hostname:', hostname);
  console.log('Detected CPU model:', cpuModel);

  const raw = stableId
    ? `${stableId}|${hostname}|${cpuModel}`
    : `${hostname}|${cpuModel}`;
  console.log('Raw fingerprint string:', raw);

  return crypto.createHash('sha256').update(raw).digest('hex');
}

module.exports = { getMachineId };
