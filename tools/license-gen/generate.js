#!/usr/bin/env node
/**
 * generate.js - 厂商许可证签名生成工具
 * 用法: node generate.js --machine-id <id> --customer <name> --expires <YYYY-MM-DD> [--out <file>]
 * 示例: node generate.js --machine-id "75a787808ffd7741a8f93d2e20705a0f3a37f4eaf7fb5e61ed6c6b8ee71f6280" --customer "某某集团" --expires "2027-03-26"
 */
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

function parseArgs() {
  const args = process.argv.slice(2);
  const result = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      result[args[i].slice(2)] = args[i + 1];
      i++;
    }
  }
  return result;
}

function signLicense(payload, privateKeyPem) {
  const data = JSON.stringify(payload, Object.keys(payload).sort());
  const sign = crypto.createSign('SHA256');
  sign.update(data);
  return sign.sign(privateKeyPem, 'base64');
}

const args = parseArgs();
const machineId = args['machine-id'];
const customer = args['customer'];
const expiresAt = args['expires'];
const outFile = args['out'] || 'license.lic';

if (!machineId || !customer || !expiresAt) {
  console.error('用法: node generate.js --machine-id <id> --customer <name> --expires <YYYY-MM-DD>');
  console.error('示例: node generate.js --machine-id "a3f8c2..." --customer "某某集团" --expires "2027-03-26"');
  process.exit(1);
}

if (!/^\d{4}-\d{2}-\d{2}$/.test(expiresAt)) {
  console.error('错误: --expires 格式必须为 YYYY-MM-DD，例如 2027-03-26');
  process.exit(1);
}

const privateKeyPath = path.join(__dirname, 'private.pem');
if (!fs.existsSync(privateKeyPath)) {
  console.error(`错误: 未找到私钥文件 ${privateKeyPath}`);
  console.error('请先运行 node keygen.js 生成密钥对');
  process.exit(1);
}

const privateKey = fs.readFileSync(privateKeyPath, 'utf8');

const issuedAt = new Date().toISOString().split('T')[0];

const payload = {
  version: 1,
  customer,
  machine_id: machineId,
  issued_at: issuedAt,
  expires_at: expiresAt,
};

const signature = signLicense(payload, privateKey);

const license = { ...payload, signature };

const outputPath = path.resolve(outFile);
fs.writeFileSync(outputPath, JSON.stringify(license, null, 2), 'utf8');

console.log('✅ 许可证生成成功');
console.log(`   文件:     ${outputPath}`);
console.log(`   客户:     ${customer}`);
console.log(`   机器 ID:  ${machineId}`);
console.log(`   签发日期: ${issuedAt}`);
console.log(`   到期日期: ${expiresAt}`);
console.log('\n将此文件通过邮件发送给客户，客户通过系统管理界面上传激活。');
