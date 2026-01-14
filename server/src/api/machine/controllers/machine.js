'use strict';

/**
 * machine controller
 */

const { createCoreController } = require('@strapi/strapi').factories;

module.exports = createCoreController('api::machine.machine');
