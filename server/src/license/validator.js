'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { getMachineId } = require('./fingerprint');

const PUBLIC_KEY_PATH = path.join(__dirname, 'public-key.pem');

let _cache = null;
let _cacheTime = 0;
const CACHE_TTL_MS = 5000;

/**
 * 验证许可证对象的签名
 */
function verifySignature(license) {
  try {
    const publicKey = fs.readFileSync(PUBLIC_KEY_PATH, 'utf8');
    const { signature, ...payload } = license;
    const data = JSON.stringify(payload, Object.keys(payload).sort());
    const verify = crypto.createVerify('SHA256');
    verify.update(data);
    return verify.verify(publicKey, signature, 'base64');
  } catch {
    return false;
  }
}

/**
 * 读取并校验许可证文件。
 * 结果缓存 5 秒（上传后调用 invalidateCache() 立即刷新）。
 *
 * 返回值结构:
 * {
 *   valid: boolean,
 *   reason: string,          // 失败原因（valid=true 时为 'ok'）
 *   customer: string,
 *   machine_id: string,
 *   issued_at: string,
 *   expires_at: string,
 *   current_machine_id: string,
 * }
 */
function validate() {
  const now = Date.now();
  if (_cache && now - _cacheTime < CACHE_TTL_MS) {
    return _cache;
  }

  const currentMachineId = getMachineId();
  const licenseFile = process.env.LICENSE_FILE || path.join(process.cwd(), 'license.lic');

  const base = {
    valid: false,
    customer: '',
    machine_id: '',
    issued_at: '',
    expires_at: '',
    current_machine_id: currentMachineId,
  };

  // 1. 文件存在性
  if (!fs.existsSync(licenseFile)) {
    _cache = { ...base, reason: 'LICENSE_NOT_FOUND' };
    _cacheTime = now;
    return _cache;
  }

  // 2. JSON 合法性
  let license;
  try {
    license = JSON.parse(fs.readFileSync(licenseFile, 'utf8'));
  } catch {
    _cache = { ...base, reason: 'LICENSE_PARSE_ERROR' };
    _cacheTime = now;
    return _cache;
  }

  const info = {
    customer: license.customer || '',
    machine_id: license.machine_id || '',
    issued_at: license.issued_at || '',
    expires_at: license.expires_at || '',
    current_machine_id: currentMachineId,
  };

  // 3. RSA 签名
  if (!verifySignature(license)) {
    _cache = { ...base, ...info, valid: false, reason: 'SIGNATURE_INVALID' };
    _cacheTime = now;
    return _cache;
  }

  // 4. 机器 ID
  if (license.machine_id !== currentMachineId) {
    _cache = { ...base, ...info, valid: false, reason: 'MACHINE_ID_MISMATCH' };
    _cacheTime = now;
    return _cache;
  }

  // 5. 有效期
  const today = new Date().toISOString().split('T')[0];
  if (!license.expires_at || license.expires_at < today) {
    _cache = { ...base, ...info, valid: false, reason: 'LICENSE_EXPIRED' };
    _cacheTime = now;
    return _cache;
  }

  _cache = { ...info, valid: true, reason: 'ok' };
  _cacheTime = now;
  return _cache;
}

/** 上传新许可证后调用，清除缓存使下次请求立即重新校验 */
function invalidateCache() {
  _cache = null;
  _cacheTime = 0;
}

const REASON_MESSAGES = {
  LICENSE_NOT_FOUND: '未找到许可证文件，请上传 license.lic',
  LICENSE_PARSE_ERROR: '许可证文件格式错误（不是合法的 JSON）',
  SIGNATURE_INVALID: '许可证签名验证失败（文件可能已被篡改）',
  MACHINE_ID_MISMATCH: '许可证绑定的机器与当前服务器不符',
  LICENSE_EXPIRED: '许可证已过期，请联系 WhatTech 续期',
  ok: '许可证有效',
};

function getReasonMessage(reason) {
  return REASON_MESSAGES[reason] || reason;
}

module.exports = { validate, invalidateCache, getReasonMessage };
