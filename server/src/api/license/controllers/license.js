'use strict';

const fs = require('fs');
const path = require('path');
const { validate, invalidateCache, getReasonMessage } = require('../../../license/validator');
const { getMachineId } = require('../../../license/fingerprint');

module.exports = {
  /**
   * GET /api/license/status
   * 返回当前许可证状态（无需认证）
   */
  async status(ctx) {
    const result = validate();
    ctx.body = {
      valid: result.valid,
      reason: result.reason,
      message: getReasonMessage(result.reason),
      customer: result.customer,
      issued_at: result.issued_at,
      expires_at: result.expires_at,
      current_machine_id: result.current_machine_id,
    };
  },

  /**
   * POST /api/license/upload
   * 接收许可证 JSON 对象，保存到 LICENSE_FILE 路径，立即重新校验。
   * 请求体: { license: { version, customer, machine_id, ... , signature } }
   */
  async upload(ctx) {
    const { license } = ctx.request.body || {};

    if (!license || typeof license !== 'object') {
      ctx.status = 400;
      ctx.body = { error: 'INVALID_REQUEST', message: '请提供许可证内容（JSON 对象）' };
      return;
    }

    const required = ['version', 'customer', 'machine_id', 'issued_at', 'expires_at', 'signature'];
    for (const field of required) {
      if (!license[field]) {
        ctx.status = 400;
        ctx.body = { error: 'MISSING_FIELD', message: `许可证缺少字段: ${field}` };
        return;
      }
    }

    const licenseFile = process.env.LICENSE_FILE || path.join(process.cwd(), 'license.lic');

    try {
      const dir = path.dirname(licenseFile);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(licenseFile, JSON.stringify(license, null, 2), 'utf8');
    } catch (err) {
      ctx.status = 500;
      ctx.body = { error: 'SAVE_FAILED', message: `保存许可证文件失败: ${err.message}` };
      return;
    }

    // 清除缓存，立即重新校验
    invalidateCache();
    const result = validate();

    if (!result.valid) {
      // 校验失败：删除已保存的文件，避免留下无效许可证
      try { fs.unlinkSync(licenseFile); } catch {}
      invalidateCache();

      ctx.status = 422;
      ctx.body = {
        error: 'VALIDATION_FAILED',
        reason: result.reason,
        message: getReasonMessage(result.reason),
        current_machine_id: getMachineId(),
      };
      return;
    }

    ctx.body = {
      success: true,
      message: '许可证激活成功',
      customer: result.customer,
      expires_at: result.expires_at,
    };
  },
};
