'use strict';

/**
 * machine router
 */

const { createCoreRouter } = require('@strapi/strapi').factories;

module.exports = createCoreRouter('api::machine.machine');
