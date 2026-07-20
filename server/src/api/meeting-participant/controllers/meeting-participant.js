'use strict';

const { createCoreController } = require('@strapi/strapi').factories;

const POPULATE = {
  user: { populate: { appRole: true, projectGroups: true } },
  headset: { populate: { machine: true } },
  machine: true,
  meeting: true,
};

module.exports = createCoreController('api::meeting-participant.meeting-participant', ({ strapi }) => ({
  async find(ctx) {
    const list = await strapi.entityService.findMany('api::meeting-participant.meeting-participant', {
      sort: { createdAt: 'asc' },
      populate: POPULATE,
    });
    ctx.body = { data: list };
  },

  async findOne(ctx) {
    const { id } = ctx.params;
    const entry = await strapi.entityService.findOne('api::meeting-participant.meeting-participant', id, {
      populate: POPULATE,
    });
    if (!entry) return ctx.notFound();
    ctx.body = { data: entry };
  },

  async delete(ctx) {
    const { id } = ctx.params;
    const target = await strapi.entityService.findOne('api::meeting-participant.meeting-participant', id);
    if (!target) return ctx.notFound();
    await strapi.entityService.delete('api::meeting-participant.meeting-participant', id);
    ctx.body = { data: { id } };
  },
}));
