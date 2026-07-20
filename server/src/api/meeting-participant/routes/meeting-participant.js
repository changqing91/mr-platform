'use strict';

const { createCoreRouter } = require('@strapi/strapi').factories;

const noAuth = { auth: false, policies: [], middlewares: [] };

module.exports = createCoreRouter('api::meeting-participant.meeting-participant', {
  config: {
    find:    noAuth,
    findOne: noAuth,
    delete:  noAuth,
  },
});
