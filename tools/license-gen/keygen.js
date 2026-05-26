#!/usr/bin/env node
/**
 * keygen.js - 一次性生成 RSA-2048 密钥对
 * 用法: node keygen.js
 * 输出: private.pem (私钥，保密) 和 public.pem (公钥，可公开)
 */
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

const dir = __dirname;
const serverPubKeyPath = path.join(dir, '..', '..', 'server', 'src', 'license', 'public-key.pem');

fs.writeFileSync(path.join(dir, 'private.pem'), privateKey, { mode: 0o600 });
fs.writeFileSync(path.join(dir, 'public.pem'), publicKey);
fs.writeFileSync(serverPubKeyPath, publicKey);

console.log('✅ 密钥对生成成功');
console.log(`   私钥: ${path.join(dir, 'private.pem')}  ← 妥善保管，绝不外发`);
console.log(`   公钥: ${path.join(dir, 'public.pem')}`);
console.log(`   公钥: ${serverPubKeyPath}  ← 已自动同步`);
console.log('\n⚠️  所有旧许可证已失效，请用新私钥重新签发。');
