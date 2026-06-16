'use strict';

const { createCoreController } = require('@strapi/strapi').factories;
const { requireManager } = require('../../../utils/auth');

module.exports = createCoreController('api::app-role.app-role', ({ strapi }) => ({
  async find(ctx) {
    if (requireManager(ctx)) return;
    const entries = await strapi.entityService.findMany('api::app-role.app-role', {
      sort: { createdAt: 'asc' },
      populate: { users: { count: true } },
    });
    // attach userCount
    const list = await Promise.all(entries.map(async (r) => {
      const count = await strapi.db.query('api::app-user.app-user').count({
        where: { appRole: r.id },
      });
      return { ...r, userCount: count };
    }));
    ctx.body = { data: list };
  },

  async findOne(ctx) {
    if (requireManager(ctx)) return;
    return super.findOne(ctx);
  },

  async create(ctx) {
    if (requireManager(ctx)) return;
    const data = ctx.request.body?.data || ctx.request.body || {};
    const name = (data.name || '').trim();
    if (!name) return ctx.badRequest('角色名称必填');

    const existing = await strapi.db.query('api::app-role.app-role').findOne({ where: { name } });
    if (existing) return ctx.conflict('角色名称已存在');

    const created = await strapi.entityService.create('api::app-role.app-role', {
      data: {
        name,
        canManage: !!data.canManage,
        isSystem: false,
      },
    });
    ctx.body = { data: created };
  },

  async update(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const data = ctx.request.body?.data || ctx.request.body || {};

    const target = await strapi.entityService.findOne('api::app-role.app-role', id);
    if (!target) return ctx.notFound();

    const patch = {};
    if (typeof data.name === 'string' && data.name.trim() && data.name.trim() !== target.name) {
      const dup = await strapi.db.query('api::app-role.app-role').findOne({
        where: { name: data.name.trim(), id: { $ne: target.id } },
      });
      if (dup) return ctx.conflict('角色名称已存在');
      patch.name = data.name.trim();
    }
    if (typeof data.canManage === 'boolean' && !target.isSystem) {
      patch.canManage = data.canManage;
    }

    const updated = await strapi.entityService.update('api::app-role.app-role', id, {
      data: patch,
    });
    ctx.body = { data: updated };
  },

  async delete(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const target = await strapi.entityService.findOne('api::app-role.app-role', id);
    if (!target) return ctx.notFound();
    if (target.isSystem) return ctx.badRequest('系统内置角色不可删除');

    const inUse = await strapi.db.query('api::app-user.app-user').count({
      where: { appRole: target.id },
    });
    if (inUse > 0) return ctx.conflict('该角色仍有用户绑定，无法删除');

    await strapi.entityService.delete('api::app-role.app-role', id);
    ctx.body = { data: { id } };
  },
}));
