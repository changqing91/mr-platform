'use strict';

const { createCoreController } = require('@strapi/strapi').factories;
const { requireAuthenticated, isManager } = require('../../../utils/auth');

const resolveGroupId = async (docId) => {
  if (!docId) return null;
  const list = await strapi.entityService.findMany('api::project-group.project-group', {
    filters: { documentId: docId },
    fields: ['id'],
    limit: 1,
  });
  return Array.isArray(list) && list[0] ? list[0].id : null;
};

const buildSort = (sortStr) => {
  if (!sortStr) return { createdAt: 'DESC' };
  const parts = sortStr.split(':');
  const field = parts[0];
  const order = (parts[1] || 'asc').toUpperCase();
  return { [field]: order };
};

module.exports = createCoreController('api::project.project', ({ strapi }) => ({
  async find(ctx) {
    if (requireAuthenticated(ctx)) return;

    const page = Math.max(1, parseInt(ctx.query.pagination?.page, 10) || 1);
    const pageSize = Math.min(100, Math.max(1, parseInt(ctx.query.pagination?.pageSize, 10) || 20));
    const sort = ctx.query.sort || 'createdAt:desc';
    const offset = (page - 1) * pageSize;
    const orderBy = buildSort(sort);
    const groupDocId = ctx.query.filters?.projectGroup?.$eq || ctx.query.filters?.projectGroup || null;

    if (!isManager(ctx)) {
      const appUserId = ctx.state.user.appUser?.id;

      if (!appUserId) {
        return ctx.send({ data: [], meta: { pagination: { page, pageSize, pageCount: 0, total: 0 } } });
      }

      const groups = await strapi.db.query('api::project-group.project-group').findMany({
        where: { users: { id: appUserId } },
        select: ['documentId'],
      });
      let groupDocIds = Array.isArray(groups) && groups.length > 0
        ? groups.map((g) => g.documentId)
        : [];

      if (groupDocIds.length === 0) {
        return ctx.send({ data: [], meta: { pagination: { page, pageSize, pageCount: 0, total: 0 } } });
      }

      if (groupDocId) {
        groupDocIds = groupDocIds.includes(groupDocId) ? [groupDocId] : [];
        if (groupDocIds.length === 0) {
          return ctx.send({ data: [], meta: { pagination: { page, pageSize, pageCount: 0, total: 0 } } });
        }
      }

      const where = { projectGroup: { documentId: { $in: groupDocIds } } };
      const count = await strapi.db.query('api::project.project').count({ where });
      const results = await strapi.db.query('api::project.project').findMany({
        where,
        populate: { projectGroup: true },
        orderBy,
        offset,
        limit: pageSize,
      });

      const pageCount = Math.ceil(count / pageSize) || 1;
      return ctx.send({ data: results, meta: { pagination: { page, pageSize, pageCount, total: count } } });
    }

    const where = groupDocId ? { projectGroup: { documentId: groupDocId } } : {};
    const count = await strapi.db.query('api::project.project').count({ where });
    const results = await strapi.db.query('api::project.project').findMany({
      where,
      populate: { projectGroup: true },
      orderBy,
      offset,
      limit: pageSize,
    });
    const pageCount = Math.ceil(count / pageSize) || 1;
    return ctx.send({ data: results, meta: { pagination: { page, pageSize, pageCount, total: count } } });
  },

  async findOne(ctx) {
    if (requireAuthenticated(ctx)) return;
    const { id } = ctx.params;
    const entry = await strapi.entityService.findOne('api::project.project', id, {
      populate: { projectGroup: { populate: { users: { fields: ['id'] } } } },
    });
    if (!entry) return ctx.notFound();

    if (!isManager(ctx)) {
      const appUserId = ctx.state.user.appUser?.id;
      const inGroup = entry.projectGroup?.users?.some((u) => u.id === appUserId);
      if (!inGroup) return ctx.forbidden('无访问权限');
    }
    return super.findOne(ctx);
  },

  async create(ctx) {
    if (requireAuthenticated(ctx)) return;
    try {
      const body = ctx.request.body?.data || ctx.request.body || {};
      const projectGroupDocId = body.projectGroup || null;
      delete body.projectGroup;

      const created = await strapi.entityService.create('api::project.project', {
        data: body,
      });

      if (projectGroupDocId) {
        const groupId = await resolveGroupId(projectGroupDocId);
        if (groupId) {
          await strapi.db.query('api::project.project').update({
            where: { id: created.id },
            data: { projectGroup: groupId },
          });
        }
      }

      const result = await strapi.entityService.findOne('api::project.project', created.id, {
        populate: { projectGroup: true },
      });
      return ctx.send({ data: result });
    } catch (err) {
      strapi.log.error('[project.create] failed', err);
      return ctx.badRequest(err.message);
    }
  },

  async update(ctx) {
    if (requireAuthenticated(ctx)) return;
    try {
      const { documentId } = ctx.params;
      const body = ctx.request.body?.data || ctx.request.body || {};
      const projectGroupDocId = body.projectGroup;
      delete body.projectGroup;

      if (projectGroupDocId !== undefined) {
        let groupId = null;
        if (projectGroupDocId) {
          groupId = await resolveGroupId(projectGroupDocId);
        }
        const [entry] = await strapi.db.query('api::project.project').findMany({
          where: { documentId },
          select: ['id'],
          limit: 1,
        });
        if (entry) {
          await strapi.db.query('api::project.project').update({
            where: { id: entry.id },
            data: { projectGroup: groupId },
          });
        }
      }

      if (Object.keys(body).length > 0) {
        const entry = await strapi.entityService.findMany('api::project.project', {
          filters: { documentId },
          limit: 1,
        });
        if (entry && entry[0]) {
          await strapi.entityService.update('api::project.project', entry[0].id, {
            data: body,
          });
        }
      }

      const refreshed = await strapi.entityService.findMany('api::project.project', {
        filters: { documentId },
        populate: { projectGroup: true },
        limit: 1,
      });
      const result = Array.isArray(refreshed) && refreshed[0] ? refreshed[0] : null;
      return ctx.send({ data: result });
    } catch (err) {
      strapi.log.error('[project.update] failed', err);
      return ctx.badRequest(err.message);
    }
  },

  async delete(ctx) {
    if (requireAuthenticated(ctx)) return;
    return super.delete(ctx);
  },
}));
