'use strict';

const cfg = { auth: false, policies: [], middlewares: [] };

module.exports = {
  routes: [
    { method: 'GET',    path: '/project-groups',     handler: 'project-group.find',    config: cfg },
    { method: 'GET',    path: '/project-groups/:id', handler: 'project-group.findOne', config: cfg },
    { method: 'POST',   path: '/project-groups',     handler: 'project-group.create',  config: cfg },
    { method: 'PUT',    path: '/project-groups/:id', handler: 'project-group.update',  config: cfg },
    { method: 'DELETE', path: '/project-groups/:id', handler: 'project-group.delete',  config: cfg },
  ],
};
