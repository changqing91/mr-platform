'use strict';

module.exports = {
  routes: [
    {
      method: 'POST',
      path: '/processes/launch',
      handler: 'process.launch',
    },
    {
      method: 'POST',
      path: '/processes/kill',
      handler: 'process.kill',
    },
    {
      method: 'POST',
      path: '/processes/kill-all',
      handler: 'process.killAll',
    },
    {
      method: 'POST',
      path: '/processes/batch-kill',
      handler: 'process.batchKill',
    },
    {
      method: 'POST',
      path: '/processes/execute-python',
      handler: 'process.executePython',
    }
  ]
};
