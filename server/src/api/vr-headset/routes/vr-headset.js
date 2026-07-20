'use strict';

const { createCoreRouter } = require('@strapi/strapi').factories;

const noAuth = { auth: false, policies: [], middlewares: [] };

module.exports = createCoreRouter('api::vr-headset.vr-headset', {
  config: {
    find:    noAuth,
    findOne: noAuth,
    create:  noAuth,
    update:  noAuth,
    delete:  noAuth,
  },
});
