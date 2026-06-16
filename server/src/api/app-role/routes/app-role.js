'use strict';

const cfg = { auth: false, policies: [], middlewares: [] };

module.exports = {
  routes: [
    { method: 'GET',    path: '/app-roles',     handler: 'app-role.find',     config: cfg },
    { method: 'GET',    path: '/app-roles/:id', handler: 'app-role.findOne',  config: cfg },
    { method: 'POST',   path: '/app-roles',     handler: 'app-role.create',   config: cfg },
    { method: 'PUT',    path: '/app-roles/:id', handler: 'app-role.update',   config: cfg },
    { method: 'DELETE', path: '/app-roles/:id', handler: 'app-role.delete',   config: cfg },
  ],
};
