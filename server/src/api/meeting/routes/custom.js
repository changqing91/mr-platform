'use strict';

const cfg = { auth: false, policies: [], middlewares: [] };

module.exports = {
  routes: [
    { method: 'POST',   path: '/meetings',                        handler: 'meeting.create',           config: cfg },
    { method: 'GET',    path: '/meetings/active',                  handler: 'meeting.findActive',       config: cfg },
    { method: 'GET',    path: '/meetings/visible-users',           handler: 'meeting.visibleUsers',     config: cfg },
    { method: 'GET',    path: '/meetings/:id',                     handler: 'meeting.findOne',          config: cfg },
    { method: 'POST',   path: '/meetings/:id/participants',        handler: 'meeting.addParticipant',   config: cfg },
    { method: 'DELETE', path: '/meetings/:id/participants/:pid',   handler: 'meeting.removeParticipant',config: cfg },
    { method: 'PUT',    path: '/meetings/:id/participants/:pid',   handler: 'meeting.updateParticipant',config: cfg },
    { method: 'POST',   path: '/meetings/:id/end',                 handler: 'meeting.end',              config: cfg },
  ],
};
