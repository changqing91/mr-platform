#!/usr/bin/env node
/**
 * fingerprint.js - 采集当前机器的硬件指纹
 * 客户在目标部署机器上运行此脚本，将输出的 machine_id 发送给厂商申请许可证。
 * 用法: node fingerprint.js
 */
'use strict';

const os = require('os');
const crypto = require('crypto');

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

const machineId = getMachineId();

console.log('=== WhatTech MR Platform - 机器指纹采集 ===\n');
console.log(`主机名:    ${os.hostname()}`);
console.log(`操作系统:  ${os.platform()} ${os.release()}`);
console.log(`CPU:       ${(os.cpus()[0] && os.cpus()[0].model) || 'unknown'}`);

const interfaces = os.networkInterfaces();
for (const [name, ifaceList] of Object.entries(interfaces)) {
  for (const iface of ifaceList) {
    if (!iface.internal && iface.mac && iface.mac !== '00:00:00:00:00:00') {
      console.log(`网卡 ${name}: ${iface.mac}`);
    }
  }
}

console.log('\n─────────────────────────────────────────────');
console.log(`机器 ID:   ${machineId}`);
console.log('─────────────────────────────────────────────');
console.log('\n请将上方「机器 ID」发送给 WhatTech 申请许可证。');
