'use strict';

const { createCoreController } = require('@strapi/strapi').factories;
const { requireAuthenticated, requireManager, isManager } = require('../../../utils/auth');

module.exports = createCoreController('api::project-group.project-group', ({ strapi }) => ({
  async find(ctx) {
    if (requireAuthenticated(ctx)) return;

    const manager = isManager(ctx);
    let filters = {};

    if (!manager) {
      const appUser = ctx.state.user.appUser;
      if (!appUser) {
        ctx.body = { data: [] };
        return;
      }
      filters = { users: { id: appUser.id } };
    }

    const list = await strapi.entityService.findMany('api::project-group.project-group', {
      filters,
      sort: { createdAt: 'asc' },
      populate: manager ? { users: { fields: ['id', 'username', 'displayName'] } } : {},
    });

    const enriched = await Promise.all(list.map(async (g) => {
      const projectCount = await strapi.db.query('api::project.project').count({
        where: { projectGroup: g.id },
      });
      return { ...g, projectCount };
    }));
    const totalProjects = await strapi.db.query('api::project.project').count(
      manager ? {} : { where: { projectGroup: { documentId: { $in: list.map(g => g.documentId) } } } }
    );
    ctx.body = { data: enriched, meta: { totalProjects } };
  },

  async findOne(ctx) {
    if (requireManager(ctx)) return;
    return super.findOne(ctx);
  },

  async create(ctx) {
    if (requireManager(ctx)) return;
    const data = ctx.request.body?.data || ctx.request.body || {};
    const name = (data.name || '').trim();
    if (!name) return ctx.badRequest('项目组名称必填');

    const created = await strapi.entityService.create('api::project-group.project-group', {
      data: {
        name,
        users: Array.isArray(data.users) ? data.users : [],
      },
    });
    ctx.body = { data: created };
  },

  async update(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const data = ctx.request.body?.data || ctx.request.body || {};
    const target = await strapi.entityService.findOne('api::project-group.project-group', id);
    if (!target) return ctx.notFound();

    const patch = {};
    if (typeof data.name === 'string' && data.name.trim()) patch.name = data.name.trim();
    if (Array.isArray(data.users)) patch.users = data.users;

    const updated = await strapi.entityService.update('api::project-group.project-group', id, {
      data: patch,
    });
    ctx.body = { data: updated };
  },

  async delete(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const target = await strapi.entityService.findOne('api::project-group.project-group', id);
    if (!target) return ctx.notFound();

    const projectCount = await strapi.db.query('api::project.project').count({
      where: { projectGroup: target.id },
    });
    if (projectCount > 0) return ctx.conflict('该项目组下仍有项目，无法删除');

    await strapi.entityService.delete('api::project-group.project-group', id);
    ctx.body = { data: { id } };
  },
}));
