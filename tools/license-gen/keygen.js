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
fs.writeFileSync(path.join(dir, 'private.pem'), privateKey, { mode: 0o600 });
fs.writeFileSync(path.join(dir, 'public.pem'), publicKey);

console.log('✅ 密钥对生成成功');
console.log(`   私钥: ${path.join(dir, 'private.pem')}  ← 妥善保管，绝不外发`);
console.log(`   公钥: ${path.join(dir, 'public.pem')}   ← 复制到 server/src/license/public-key.pem`);
console.log('\n将公钥复制到软件中:');
console.log(`  cp ${path.join(dir, 'public.pem')} ../../server/src/license/public-key.pem`);
