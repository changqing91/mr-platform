'use strict';

module.exports = {
  routes: [
    {
      method: 'GET',
      path: '/user-admin/users',
      handler: 'user-admin.listUsers',
      config: {
        policies: [],
        middlewares: [],
      },
    },
    {
      method: 'PUT',
      path: '/user-admin/users/:id/password',
      handler: 'user-admin.changePassword',
      config: {
        policies: [],
        middlewares: [],
      },
    },
  ],
};
