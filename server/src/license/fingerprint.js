'use strict';

const os = require('os');
const crypto = require('crypto');

/**
 * 采集当前服务器的硬件指纹。
 * 算法与 tools/license-gen/fingerprint.js 保持完全一致。
 */
function getMachineId() {
  const interfaces = os.networkInterfaces();
  const macs = [];

  const seen = new Set();
  for (const ifaceList of Object.values(interfaces)) {
    for (const iface of ifaceList) {
      if (!iface.internal && iface.mac && iface.mac !== '00:00:00:00:00:00' && !seen.has(iface.mac)) {
        seen.add(iface.mac);
        macs.push(iface.mac.toLowerCase());
      }
    }
  }
  macs.sort();

  const hostname = os.hostname();
  const cpuModel = (os.cpus()[0] && os.cpus()[0].model) || 'unknown';
  const raw = `${macs.join('|')}|${hostname}|${cpuModel}`;

  return crypto.createHash('sha256').update(raw).digest('hex');
}

module.exports = { getMachineId };
