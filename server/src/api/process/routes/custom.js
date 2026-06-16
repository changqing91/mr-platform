'use strict';

const cfg = { auth: false, policies: [], middlewares: [] };

module.exports = {
  routes: [
    { method: 'POST', path: '/processes/launch',         handler: 'process.launch',          config: cfg },
    { method: 'POST', path: '/processes/kill',           handler: 'process.kill',            config: cfg },
    { method: 'POST', path: '/processes/kill-all',       handler: 'process.killAll',         config: cfg },
    { method: 'POST', path: '/processes/batch-kill',     handler: 'process.batchKill',       config: cfg },
    { method: 'POST', path: '/processes/execute-python', handler: 'process.executePython',   config: cfg },
    { method: 'GET',  path: '/processes/script-config',  handler: 'process.getScriptConfig', config: cfg },
    { method: 'PUT',  path: '/processes/script-config',  handler: 'process.saveScriptConfig',config: cfg },
  ],
};
