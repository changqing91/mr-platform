'use strict';

const { createCoreController } = require('@strapi/strapi').factories;
const { requireManager } = require('../../../utils/auth');

const POPULATE = {
  machine: true,
};

module.exports = createCoreController('api::vr-headset.vr-headset', ({ strapi }) => ({
  async find(ctx) {
    const list = await strapi.entityService.findMany('api::vr-headset.vr-headset', {
      sort: { createdAt: 'asc' },
      populate: POPULATE,
    });
    ctx.body = { data: list };
  },

  async findOne(ctx) {
    const { id } = ctx.params;
    const entry = await strapi.entityService.findOne('api::vr-headset.vr-headset', id, {
      populate: POPULATE,
    });
    if (!entry) return ctx.notFound();
    ctx.body = { data: entry };
  },

  async create(ctx) {
    if (requireManager(ctx)) return;
    const data = ctx.request.body?.data || ctx.request.body || {};
    const created = await strapi.entityService.create('api::vr-headset.vr-headset', {
      data: {
        name: data.name,
        type: data.type || 'Vive',
        serialNumber: data.serialNumber || null,
        status: data.status || 'idle',
        machine: data.machineId || null,
      },
      populate: POPULATE,
    });
    ctx.body = { data: created };
  },

  async update(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const data = ctx.request.body?.data || ctx.request.body || {};
    const patch = {};
    if (data.name !== undefined) patch.name = data.name;
    if (data.type !== undefined) patch.type = data.type;
    if (data.serialNumber !== undefined) patch.serialNumber = data.serialNumber;
    if (data.status !== undefined) patch.status = data.status;
    if (data.machineId !== undefined) patch.machine = data.machineId || null;

    const updated = await strapi.entityService.update('api::vr-headset.vr-headset', id, {
      data: patch,
      populate: POPULATE,
    });
    ctx.body = { data: updated };
  },

  async delete(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const target = await strapi.entityService.findOne('api::vr-headset.vr-headset', id);
    if (!target) return ctx.notFound();
    if (target.status === 'in-use') {
      return ctx.badRequest('头盔正在使用中，无法删除');
    }
    await strapi.entityService.delete('api::vr-headset.vr-headset', id);
    ctx.body = { data: { id } };
  },
}));
