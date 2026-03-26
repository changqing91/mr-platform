'use strict';

const { validate } = require('../license/validator');

/**
 * license-check - 全局许可证校验中间件
 *
 * 放行:
 *   - 所有非 /api/* 请求（admin 面板、静态资源等）
 *   - /api/license/* 端点（status 查询 & 文件上传）
 *
 * 拦截:
 *   - 许可证无效或过期时，所有其他 /api/* 请求返回 HTTP 403
 */
module.exports = (_config, _helpers) => {
  return async (ctx, next) => {
    const { path } = ctx.request;

    // 放行非 API 路径和许可证自身端点
    if (!path.startsWith('/api/') || path.startsWith('/api/license')) {
      return next();
    }

    const result = validate();

    if (!result.valid) {
      ctx.status = 403;
      ctx.body = {
        error: 'LICENSE_INVALID',
        reason: result.reason,
        message: result.reason === 'LICENSE_NOT_FOUND'
          ? '系统未授权，请上传许可证文件'
          : result.reason === 'LICENSE_EXPIRED'
            ? '许可证已过期，请续期'
            : '许可证无效',
      };
      return;
    }

    return next();
  };
};
