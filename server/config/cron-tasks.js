const net = require('net');

const pingByIpAndPort = (ip, port) => {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(2000); // 2s timeout

    socket.on('connect', () => {
      socket.destroy();
      resolve(true);
    });

    socket.on('timeout', () => {
      socket.destroy();
      resolve(false);
    });

    socket.on('error', (err) => {
      socket.destroy();
      resolve(false);
    });

    socket.connect(port, ip);
  });
};

module.exports = {
  checkStartingProcesses: {
    task: async ({ strapi }) => {
      try {
        // Find processes with status 'starting'
        const processes = await strapi.entityService.findMany("api::process.process", {
          filters: { status: 'starting' },
          populate: ['machine']
        });

        for (const process of processes) {
          if (process.machine && process.machine.ip && process.machine.port) {
            const isRun = await pingByIpAndPort(process.machine.ip, process.machine.port);
            if (isRun) {
              console.log(`Process ${process.id} (Machine ${process.machine.name}:${process.machine.port}) is now running.`);

              await strapi.entityService.update("api::process.process", process.id, {
                data: { status: 'running' }
              });
              
              // Also update machine status if needed, though launch controller does this.
              // But strictly speaking, if it was starting, machine might be 'running' (as in occupied).
            }
          }
        }
      } catch (error) {
        console.error('Cron job error:', error);
      }
    },
    options: {
      rule: "*/2 * * * * *", // Every 2 seconds
    },
  },
};
