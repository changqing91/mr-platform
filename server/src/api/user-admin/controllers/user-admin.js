'use strict';

module.exports = {
  /**
   * GET /api/user-admin/users
   * 列出所有注册用户（仅限管理员）
   */
  async listUsers(ctx) {
    if (!ctx.state.user || ctx.state.user.username !== 'admin') {
      return ctx.forbidden('Access denied');
    }
    const users = await strapi.db.query('plugin::users-permissions.user').findMany({
      select: ['id', 'username', 'email', 'confirmed', 'blocked', 'createdAt'],
      orderBy: { createdAt: 'asc' },
    });
    ctx.body = users;
  },

  /**
   * PUT /api/user-admin/users/:id/password
   * 修改指定用户密码（仅限管理员）
   */
  async changePassword(ctx) {
    if (!ctx.state.user || ctx.state.user.username !== 'admin') {
      return ctx.forbidden('Access denied');
    }
    const { id } = ctx.params;
    const { password } = ctx.request.body || {};

    if (!password || typeof password !== 'string' || password.length < 6) {
      return ctx.badRequest('密码长度至少为6位');
    }

    const targetUser = await strapi.db.query('plugin::users-permissions.user').findOne({
      where: { id },
    });

    if (!targetUser) {
      return ctx.notFound('用户不存在');
    }

    // entityService handles password hashing
    await strapi.entityService.update('plugin::users-permissions.user', id, {
      data: { password },
    });

    ctx.body = { message: '密码已更新' };
  },
};
