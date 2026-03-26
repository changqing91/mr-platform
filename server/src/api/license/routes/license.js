'use strict';

module.exports = {
  routes: [
    {
      method: 'GET',
      path: '/license/status',
      handler: 'license.status',
      config: {
        auth: false,
        policies: [],
        middlewares: [],
      },
    },
    {
      method: 'POST',
      path: '/license/upload',
      handler: 'license.upload',
      config: {
        auth: false,
        policies: [],
        middlewares: [],
      },
    },
  ],
};
