'use strict';

// @ts-ignore
const { createCoreController } = require('@strapi/strapi').factories;
const http = require('http');

const terminateProcess = async (strapi, processEntity) => {
    const machine = processEntity.machine;
    const agentPort = process.env.AGENT_PORT || 8099;

    if (processEntity.pid) {
        console.log(`Killing PID ${processEntity.pid} on ${machine.ip}`);
        const killCmd = `taskkill /F /PID ${processEntity.pid}`;

        try {
            await new Promise((resolve, reject) => {
                const req = http.get(`http://${machine.ip}:${agentPort}/?command=${encodeURIComponent(killCmd)}`, (res) => {
                    let responseData = '';
                    res.on('data', (chunk) => responseData += chunk);
                    res.on('end', () => {
                        console.log('Kill Response:', responseData);
                        resolve(responseData);
                    });
                });

                req.on('error', (e) => {
                    console.error('Kill Request Error:', e);
                    // Resolve anyway to update DB status even if agent unreachable (force cleanup)
                    resolve(null);
                });

                req.setTimeout(10000, () => {
                    req.destroy();
                    resolve(null);
                });
            });
        } catch (e) {
            console.error('Kill Execution Error:', e);
        }
    }

    // Delete Process Record
    await strapi.entityService.delete('api::process.process', processEntity.id);

    // Update Machine Status
    if (machine) {
        await strapi.entityService.update('api::machine.machine', machine.id, {
            data: { 
                status: 'idle',
                current_project: null 
            }
        });
    }
};

module.exports = createCoreController('api::process.process', ({ strapi }) => ({
  async kill(ctx) {
    try {
        const { machineId } = ctx.request.body;
        if (!machineId) return ctx.badRequest('Machine ID is required');

        // Find running process for this machine
        const processes = await strapi.entityService.findMany('api::process.process', {
            filters: {
                machine: machineId,
                status: 'running'
            },
            populate: ['machine']
        });

        if (!processes || processes.length === 0) {
            return ctx.notFound('No running process found for this machine');
        }

        await Promise.all(processes.map(p => terminateProcess(strapi, p)));

        return { message: 'Process terminated' };

    } catch (error) {
        console.error('Kill Error:', error);
        return ctx.internalServerError(error.message);
    }
  },

  async killAll(ctx) {
      try {
          const processes = await strapi.entityService.findMany('api::process.process', {
              filters: { status: 'running' },
              populate: ['machine']
          });
  
          await Promise.all(processes.map(p => terminateProcess(strapi, p)));
          
          return { message: `Terminated ${processes.length} processes` };
      } catch (error) {
          console.error('KillAll Error:', error);
          return ctx.internalServerError(error.message);
      }
  },

  async batchKill(ctx) {
      try {
          const { machineIds } = ctx.request.body;
          if (!machineIds || !Array.isArray(machineIds) || machineIds.length === 0) {
              return ctx.badRequest('Machine IDs array is required');
          }

          // Find running processes for these machines
          const processes = await strapi.entityService.findMany('api::process.process', {
              filters: {
                  machine: { id: { $in: machineIds } },
                  status: 'running'
              },
              populate: ['machine']
          });

          await Promise.all(processes.map(p => terminateProcess(strapi, p)));
          
          return { message: `Terminated ${processes.length} processes` };
      } catch (error) {
          console.error('BatchKill Error:', error);
          return ctx.internalServerError(error.message);
      }
  },

  async executePython(ctx) {
      try {
          const { ip, port, code } = ctx.request.body;
          if (!ip || !code) {
              return ctx.badRequest('IP and Code are required');
          }
          const targetPort = port || 8888;
          
          console.log(`Executing Python on ${ip}:${targetPort}: ${code}`);
          
          const result = await new Promise((resolve, reject) => {
              const req = http.get(`http://${ip}:${targetPort}/python?value=${encodeURIComponent(code)}`, (res) => {
                  let responseData = '';
                  res.on('data', (chunk) => responseData += chunk);
                  res.on('end', () => resolve(responseData));
              });
              
              req.on('error', (e) => {
                  console.error('Python Request Error:', e);
                  reject(e);
              });
              
              req.setTimeout(5000, () => {
                  req.destroy();
                  reject(new Error('Request timeout'));
              });
          });
          
          return { message: 'Command executed', result };
      } catch (error) {
          console.error('ExecutePython Error:', error);
          return ctx.internalServerError(error.message);
      }
  },

  async launch(ctx) {
    try {
      const { machineId, projectId } = ctx.request.body;

      if (!machineId || !projectId) {
        return ctx.badRequest('Machine ID and Project ID are required');
      }

      // Fetch Machine and Project
      const machine = await strapi.entityService.findOne('api::machine.machine', machineId);
      const project = await strapi.entityService.findOne('api::project.project', projectId);

      if (!machine) return ctx.notFound('Machine not found');
      if (!project) return ctx.notFound('Project not found');

      // Check for existing running/starting process and terminate it
      const existingProcesses = await strapi.entityService.findMany('api::process.process', {
          filters: {
              machine: machineId,
              status: { $in: ['running', 'starting'] }
          },
          populate: ['machine']
      });

      if (existingProcesses && existingProcesses.length > 0) {
          console.log(`Found ${existingProcesses.length} existing processes for machine ${machineId}, terminating...`);
          await Promise.all(existingProcesses.map(p => terminateProcess(strapi, p)));
      }

      // Construct Command
      const agentPort = process.env.AGENT_PORT || 8099;
      const vredPort = machine.port || 8888;
      const vredBin = process.env.VRED_BIN || '';
      const startupScript = process.env.VRED_STARTUP_SCRIPT || '';
      const finalPath = project.filePath || project.fileName || project.name;
      
      const cmd = `${vredBin} -wport=${vredPort} -script "${startupScript}" "${finalPath}"`;
      
      console.log(`Executing command on ${machine.ip}: ${cmd}`);

      // Launch Process via Agent
      const pid = await new Promise((resolve, reject) => {
        let responseData = '';
        const req = http.get(`http://${machine.ip}:${agentPort}/?command=${encodeURIComponent(cmd)}`, (res) => {
          res.on('data', (chunk) => responseData += chunk);
          res.on('end', () => {
             try {
                console.log('Agent Response:', responseData);
                const pidMatch = responseData.match(/PID[:\s]+(\d+)/i) || responseData.match(/(\d+)/);
                const extractedPid = pidMatch ? pidMatch[1] : null;
                
                if (!extractedPid) {
                    try {
                        const json = JSON.parse(responseData);
                        if (json.pid) resolve(json.pid);
                        else resolve(null);
                    } catch(e) { resolve(null); }
                } else {
                    resolve(extractedPid);
                }
             } catch (e) {
                 console.error('PID Parse Error:', e);
                 resolve(null);
             }
          });
        });

        req.on('error', (e) => {
            console.error('Agent Request Error:', e);
            reject(e);
        });
        
        req.setTimeout(30000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
      });

      console.log(`Process launched, PID: ${pid}`);

      // Create Process Entry
      const newProcess = await strapi.entityService.create('api::process.process', {
        data: {
          machine: machineId,
          project: projectId,
          pid: pid ? String(pid) : null,
          status: pid ? 'starting' : 'error',
          startTime: new Date(),
        }
      });

      return this.transformResponse(newProcess);

    } catch (error) {
      console.error('Launch Error:', error);
      return ctx.internalServerError(error.message);
    }
  },

}));
