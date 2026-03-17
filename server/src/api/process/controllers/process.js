'use strict';

// @ts-ignore
const { createCoreController } = require('@strapi/strapi').factories;
const http = require('http');

/**
 * 向 VRED 发送单条 Python 命令 (GET /python?value=...)
 * @param {string} ip   VRED 主机 IP
 * @param {number} port VRED WebInterface 端口
 * @param {string} code Python 代码 (短)
 * @param {number} timeout 超时毫秒数，默认 5000
 * @returns {Promise<string>}
 */
const sendPythonToVRED = (ip, port, code, timeout = 5000) => {
    return new Promise((resolve, reject) => {
        const url = `http://${ip}:${port}/python?value=${encodeURIComponent(code)}`;
        const req = http.get(url, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => resolve(data));
        });
        req.on('error', (e) => {
            console.error('Python Request Error:', e);
            reject(e);
        });
        req.setTimeout(timeout, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
    });
};

/**
 * 安全限制: VRED Beast HTTP 对请求头 (含 URL) 有 ~8KB 限制。
 * 当 URL 编码后超过此阈值时，将代码 base64 编码后分块发送，
 * 最后在 VRED 中 decode + exec。
 */
const MAX_SAFE_URL_CODE_LENGTH = 4000;
const B64_CHUNK_SIZE = 6000;

/**
 * 向 VRED 执行 Python 代码，自动处理大代码分块
 */
const executePythonOnVRED = async (ip, port, code) => {
    const encodedLength = encodeURIComponent(code).length;

    // ---- 小代码: 直接单次请求 ----
    if (encodedLength <= MAX_SAFE_URL_CODE_LENGTH) {
        return sendPythonToVRED(ip, port, code);
    }

    // ---- 大代码: base64 分块 ----
    const b64 = Buffer.from(code, 'utf-8').toString('base64');
    const totalChunks = Math.ceil(b64.length / B64_CHUNK_SIZE);
    console.log(`[executePython] Code too large (${code.length} chars, encoded ${encodedLength}). Splitting into ${totalChunks} base64 chunks.`);

    // 第一块: 初始化变量
    const firstChunk = b64.slice(0, B64_CHUNK_SIZE);
    await sendPythonToVRED(ip, port, `_py_b64_code = "${firstChunk}"`);

    // 后续块: 追加
    for (let i = 1; i < totalChunks; i++) {
        const chunk = b64.slice(i * B64_CHUNK_SIZE, (i + 1) * B64_CHUNK_SIZE);
        await sendPythonToVRED(ip, port, `_py_b64_code += "${chunk}"`);
    }

    // 解码并执行
    const result = await sendPythonToVRED(
        ip, port,
        `exec(__import__('base64').b64decode(_py_b64_code).decode('utf-8'))`,
        30000  // 大代码执行可能需要更长时间
    );

    console.log(`[executePython] Chunked execution complete (${totalChunks} chunks)`);
    return result;
};

const terminateProcess = async (strapi, processEntity) => {
    const machine = processEntity.machine;
    const vredPort = machine.port || 8888;

    // 终止逻辑修改说明 (2025-02-04):
    // 使用 VRED Python API 直接退出 VRED 应用程序
    // 命令: terminateVred()
    const pythonCommand = 'terminateVred()';
    console.log(`Terminating VRED on ${machine.ip}:${vredPort}`);

    try {
        await new Promise((resolve, reject) => {
            const req = http.get(`http://${machine.ip}:${vredPort}/pythonasyncr?value=${encodeURIComponent(pythonCommand)}`, (res) => {
                let responseData = '';
                res.on('data', (chunk) => responseData += chunk);
                res.on('end', () => {
                    console.log('Clear Scene Response:', responseData);
                    resolve(responseData);
                });
            });

            req.on('error', (e) => {
                console.error('Clear Scene Request Error:', e);
                // Resolve anyway to update DB status even if VRED unreachable
                resolve(null);
            });

            req.setTimeout(5000, () => {
                req.destroy();
                resolve(null);
            });
        });
    } catch (e) {
        console.error('Clear Scene Execution Error:', e);
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

            console.log(`Executing Python on ${ip}:${targetPort} (${code.length} chars)`);

            const result = await executePythonOnVRED(ip, targetPort, code);

            console.log(`execute callback : ${result}`);
            return { message: 'Command executed', result };
        } catch (error) {
            console.error('ExecutePython Error:', error);
            return ctx.internalServerError(error.message);
        }
    },

    async launch(ctx) {
        /**
         * 启动逻辑修改说明 (2025-02-04):
         * 1. 不再通过 Agent 调用命令行启动 VRED 进程。
         * 2. 假设 VRED 进程已在目标机器上通过人工方式启动。
         * 3. 改为调用 VRED 内置的 WebInterface (http://ip:port/pythonasyncr) 来加载项目文件。
         * 4. 执行的 Python 指令为: vrFileIOService.loadFile("path/to/file")
         * 5. 创建的 Process 记录中 pid 为 null，因为不再管理操作系统层面的进程生命周期。
         */
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

            // // Check for existing running/starting process and terminate it
            // const existingProcesses = await strapi.entityService.findMany('api::process.process', {
            //     filters: {
            //         machine: machineId,
            //         status: { $in: ['running', 'starting'] }
            //     },
            //     populate: ['machine']
            // });

            // if (existingProcesses && existingProcesses.length > 0) {
            //     console.log(`Found ${existingProcesses.length} existing processes for machine ${machineId}, terminating...`);
            //     await Promise.all(existingProcesses.map(p => terminateProcess(strapi, p)));
            // }

            // Construct Command
            const vredPort = machine.port || 8888;
            const finalPath = project.filePath || project.fileName || project.name;

            // Ensure path format is compatible with VRED Python (forward slashes are safer)
            const sanitizedPath = finalPath.replace(/\\/g, '/');
            const isWireFile = sanitizedPath.toLowerCase().endsWith('.wire');
            const pythonCommand = isWireFile
                ? `vrLiveReferenceService.importFile("${sanitizedPath}")`
                : `vrFileIOService.newFile()\nvrFileIOService.loadFile("${sanitizedPath}")`;

            console.log(`Loading project on ${machine.ip}:${vredPort}: ${pythonCommand}`);

            // Call VRED WebInterface
            await new Promise((resolve, reject) => {
                const req = http.get(`http://${machine.ip}:${vredPort}/pythonasyncr?value=${encodeURIComponent(pythonCommand)}`, (res) => {
                    let responseData = '';
                    res.on('data', (chunk) => responseData += chunk);
                    res.on('end', () => {
                        console.log('VRED Response:', responseData);
                        resolve(responseData);
                    });
                });

                req.on('error', (e) => {
                    console.error('VRED Request Error:', e);
                    reject(e);
                });

                req.setTimeout(30000, () => {
                    req.destroy();
                    reject(new Error('Request timeout'));
                });
            });

            console.log(`Project loaded successfully`);

            // Create Process Entry
            const newProcess = await strapi.entityService.create('api::process.process', {
                data: {
                    machine: machineId,
                    project: projectId,
                    pid: null, // Managed manually
                    status: 'running',
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
