'use strict';

const cfg = { auth: false, policies: [], middlewares: [] };

module.exports = {
  routes: [
    { method: 'GET',    path: '/me',                       handler: 'app-user.me',            config: cfg },
    { method: 'GET',    path: '/app-users',                handler: 'app-user.find',          config: cfg },
    { method: 'GET',    path: '/app-users/:id',            handler: 'app-user.findOne',       config: cfg },
    { method: 'POST',   path: '/app-users',                handler: 'app-user.create',        config: cfg },
    { method: 'PUT',    path: '/app-users/:id',            handler: 'app-user.update',        config: cfg },
    { method: 'DELETE', path: '/app-users/:id',            handler: 'app-user.delete',        config: cfg },
    { method: 'PUT',    path: '/app-users/:id/password',   handler: 'app-user.resetPassword', config: cfg },
  ],
};
