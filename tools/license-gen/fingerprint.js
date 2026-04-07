#!/usr/bin/env node
/**
 * fingerprint.js - 采集当前机器的硬件指纹
 * 客户在目标部署机器上运行此脚本，将输出的 machine_id 发送给厂商申请许可证。
 * 用法: node fingerprint.js
 */
'use strict';

const os = require('os');
const fs = require('fs');
const { execSync } = require('child_process');
const crypto = require('crypto');

/**
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
  return null;
}

function getMachineId() {
  const stableId = getStableId();
  const hostname = os.hostname();
  const cpuModel = (os.cpus()[0] && os.cpus()[0].model) || 'unknown';
  const raw = stableId
    ? `${stableId}|${hostname}|${cpuModel}`
    : `${hostname}|${cpuModel}`;
  return crypto.createHash('sha256').update(raw).digest('hex');
}

const machineId = getMachineId();
const stableIdDisplay = getStableId();

console.log('=== WhatTech MR Platform - 机器指纹采集 ===\n');
console.log(`主机名:    ${os.hostname()}`);
console.log(`操作系统:  ${os.platform()} ${os.release()}`);
console.log(`CPU:       ${(os.cpus()[0] && os.cpus()[0].model) || 'unknown'}`);
if (stableIdDisplay) {
  const label = os.platform() === 'linux' ? 'machine-id' : '序列号';
  console.log(`${label}:   ${stableIdDisplay}`);
}

console.log('\n─────────────────────────────────────────────');
console.log(`机器 ID:   ${machineId}`);
console.log('─────────────────────────────────────────────');
console.log('\n请将上方「机器 ID」发送给 WhatTech 申请许可证。');
