'use strict';

/**
 * machine service
 */

const { createCoreService } = require('@strapi/strapi').factories;

module.exports = createCoreService('api::machine.machine');
