'use strict';

/**
 * process service
 */

const { createCoreService } = require('@strapi/strapi').factories;

module.exports = createCoreService('api::process.process');
