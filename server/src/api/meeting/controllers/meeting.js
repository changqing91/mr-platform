'use strict';

const { createCoreController } = require('@strapi/strapi').factories;
const http = require('http');
const { requireAuthenticated, isManager } = require('../../../utils/auth');

const POPULATE_MEETING = {
  host: { populate: { appRole: true, projectGroups: true } },
  project: true,
  hostMachine: true,
  participants: {
    populate: {
      user: { populate: { appRole: true, projectGroups: true } },
      headset: { populate: { machine: true } },
      machine: true,
    },
  },
};

const POPULATE_PARTICIPANT = {
  user: { populate: { appRole: true, projectGroups: true } },
  headset: { populate: { machine: true } },
  machine: true,
  meeting: true,
};

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

const executePythonOnVRED = async (ip, port, code) => {
  const encodedLength = encodeURIComponent(code).length;
  if (encodedLength <= 4000) {
    return sendPythonToVRED(ip, port, code);
  }
  const b64 = Buffer.from(code, 'utf-8').toString('base64');
  const totalChunks = Math.ceil(b64.length / 6000);
  const firstChunk = b64.slice(0, 6000);
  await sendPythonToVRED(ip, port, `_py_b64 = {0: "${firstChunk}"}`);
  for (let i = 1; i < totalChunks; i++) {
    const chunk = b64.slice(i * 6000, (i + 1) * 6000);
    await sendPythonToVRED(ip, port, `_py_b64[${i}] = "${chunk}"`);
  }
  return sendPythonToVRED(
    ip, port,
    `exec(__import__('base64').b64decode(''.join(_py_b64[k] for k in sorted(_py_b64))).decode('utf-8'))`,
    30000
  );
};

const joinVredSession = async (ip, port, hostIp, participantName) => {
  const safeName = (participantName || 'Participant').replace(/'/g, "\\'");
  const code = `vrSessionService.join('${hostIp}', userName='${safeName}', color=PySide2.QtGui.Qt.transparent, roomName='Autodesk', passwd='', forceVersion=False)`;
  try {
    await executePythonOnVRED(ip, port, code);
  } catch (e) {
    console.error(`[meeting] joinVredSession failed on ${ip}:${port}`, e);
  }
};

const leaveVredSession = async (ip, port) => {
  try {
    await executePythonOnVRED(ip, port, 'vrSessionService.leave()');
  } catch (e) {
    console.error(`[meeting] leaveVredSession failed on ${ip}:${port}`, e);
  }
};

const setMicEnabled = async (ip, port, enabled) => {
  const tf = enabled ? 'True' : 'False';
  const code = `vrSessionService.setAudioEnabled(${tf})\nvrSessionService.setSpeakerMute(False)\nvrSessionService.setMicrophoneMute(False)\nvrSessionService.setSpatialAudio(False)`;
  try {
    await executePythonOnVRED(ip, port, code);
  } catch (e) {
    console.error(`[meeting] setMicEnabled failed on ${ip}:${port}`, e);
  }
};

const setVrMode = async (ip, port, enabled) => {
  const code = enabled ? 'setDisplayMode(VR_DISPLAY_OPEN_VR)' : 'setDisplayMode(VR_DISPLAY_STANDARD)';
  try {
    await executePythonOnVRED(ip, port, code);
  } catch (e) {
    console.error(`[meeting] setVrMode failed on ${ip}:${port}`, e);
  }
};

const getVisibleUserIds = async (strapi, hostAppUserId) => {
  const host = await strapi.entityService.findOne('api::app-user.app-user', hostAppUserId, {
    populate: { projectGroups: true },
  });
  if (!host || !host.projectGroups || host.projectGroups.length === 0) {
    return [hostAppUserId];
  }
  const groupIds = host.projectGroups.map(g => g.id);
  const groups = await strapi.entityService.findMany('api::project-group.project-group', {
    filters: { id: { $in: groupIds } },
    populate: { users: true },
  });
  const userIds = new Set();
  for (const group of groups) {
    if (group.users) {
      group.users.forEach(u => userIds.add(u.id));
    }
  }
  return Array.from(userIds);
};

const launchProjectOnMachine = async (strapi, machineId, projectId) => {
  const machine = await strapi.entityService.findOne('api::machine.machine', machineId);
  const project = await strapi.entityService.findOne('api::project.project', projectId);

  if (!machine) throw new Error('Machine not found');
  if (!project) throw new Error('Project not found');

  const existingProcesses = await strapi.entityService.findMany('api::process.process', {
    filters: {
      machine: machineId,
      status: { $in: ['running', 'starting'] },
    },
  });

  if (existingProcesses && existingProcesses.length > 0) {
    console.log(`[meeting] Cleaning ${existingProcesses.length} existing process records for machine ${machineId}`);
    await Promise.all(existingProcesses.map(p => strapi.entityService.delete('api::process.process', p.id)));
  }

  const vredPort = machine.port || 8888;
  const finalPath = project.filePath || project.fileName || project.name;
  const sanitizedPath = finalPath.replace(/\\/g, '/');
  const isWireFile = sanitizedPath.toLowerCase().endsWith('.wire');

  try {
    await executePythonOnVRED(machine.ip, vredPort, 'vrFileIOService.newFile()');
  } catch (e) {
    console.error(`[meeting] newFile failed on ${machine.ip}:${vredPort}`, e);
  }

  if (isWireFile) {
    try {
      await executePythonOnVRED(machine.ip, vredPort, `vrLiveReferenceService.importFile("${sanitizedPath}")`);
    } catch (e) {
      console.error(`[meeting] importFile failed on ${machine.ip}:${vredPort}`, e);
    }
  } else {
    try {
      await executePythonOnVRED(machine.ip, vredPort, `vrFileIOService.loadFile("${sanitizedPath}")`);
    } catch (e) {
      console.error(`[meeting] loadFile failed on ${machine.ip}:${vredPort}`, e);
    }
  }

  await strapi.entityService.create('api::process.process', {
    data: {
      machine: machineId,
      project: projectId,
      pid: null,
      status: 'running',
      startTime: new Date(),
    },
  });

  await strapi.entityService.update('api::machine.machine', machineId, {
    data: { status: 'running', current_project: projectId },
  });

  return { machineIp: machine.ip, machinePort: vredPort };
};

const killProcessOnMachine = async (strapi, machineId) => {
  const processes = await strapi.entityService.findMany('api::process.process', {
    filters: {
      machine: machineId,
      status: { $in: ['running', 'starting'] },
    },
    populate: { machine: true },
  });

  if (!processes || processes.length === 0) return;

  await Promise.all(processes.map(async (p) => {
    if (p.machine) {
      const port = p.machine.port || 8888;
      try {
        await executePythonOnVRED(p.machine.ip, port, 'vrFileIOService.newFile()');
      } catch (e) {
        console.error(`[meeting] killProcess newFile failed on ${p.machine.ip}:${port}`, e);
      }
    }
    await strapi.entityService.delete('api::process.process', p.id);
  }));

  await strapi.entityService.update('api::machine.machine', machineId, {
    data: { status: 'idle', current_project: null },
  });
};

module.exports = createCoreController('api::meeting.meeting', ({ strapi }) => ({

  async create(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const { title, projectId, hostMachineId } = ctx.request.body;
    if (!title || !projectId || !hostMachineId) {
      return ctx.badRequest('title, projectId, and hostMachineId are required');
    }

    const me = ctx.state.user.appUser;

    const existingAsHost = await strapi.entityService.findMany('api::meeting.meeting', {
      filters: { host: me.id, status: 'active' },
    });
    if (existingAsHost && existingAsHost.length > 0) {
      return ctx.badRequest('You already have an active meeting as host');
    }

    const existingAsParticipant = await strapi.entityService.findMany('api::meeting-participant.meeting-participant', {
      filters: { user: me.id, status: { $in: ['invited', 'joined'] } },
      populate: { meeting: true },
    });
    const inActiveMeeting = existingAsParticipant.find(p => p.meeting && p.meeting.status === 'active');
    if (inActiveMeeting) {
      return ctx.badRequest('You are already in an active meeting as participant');
    }

    const meeting = await strapi.entityService.create('api::meeting.meeting', {
      data: {
        title,
        project: projectId,
        hostMachine: hostMachineId,
        host: me.id,
        status: 'active',
        roomName: 'Autodesk',
      },
      populate: POPULATE_MEETING,
    });

    try {
      await launchProjectOnMachine(strapi, hostMachineId, projectId);
    } catch (e) {
      console.error('[meeting] launchProjectOnMachine failed for host:', e);
    }

    const hostMachine = await strapi.entityService.findOne('api::machine.machine', hostMachineId);
    const hostIp = hostMachine.ip;
    const hostPort = hostMachine.port || 8888;
    const hostName = me.displayName || me.username || 'Host';

    try {
      await joinVredSession('localhost', hostPort, hostIp, hostName);
    } catch (e) {
      console.error('[meeting] host joinVredSession failed:', e);
    }

    const refreshed = await strapi.entityService.findOne('api::meeting.meeting', meeting.id, {
      populate: POPULATE_MEETING,
    });

    return this.transformResponse(refreshed);
  },

  async findActive(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const me = ctx.state.user.appUser;

    const asHost = await strapi.entityService.findMany('api::meeting.meeting', {
      filters: { host: me.id, status: 'active' },
      populate: POPULATE_MEETING,
    });

    if (asHost && asHost.length > 0) {
      return this.transformResponse(asHost[0]);
    }

    const asParticipant = await strapi.entityService.findMany('api::meeting-participant.meeting-participant', {
      filters: { user: me.id, status: { $in: ['invited', 'joined'] } },
      populate: { meeting: { populate: POPULATE_MEETING } },
    });

    const active = asParticipant.find(p => p.meeting && p.meeting.status === 'active');
    if (active) {
      return this.transformResponse(active.meeting);
    }

    return ctx.send({ data: null });
  },

  async findOne(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const { id } = ctx.params;
    const me = ctx.state.user.appUser;

    const meeting = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    if (!meeting) return ctx.notFound('Meeting not found');

    if (isManager(ctx) || (meeting.host && meeting.host.id === me.id)) {
      return this.transformResponse(meeting);
    }

    const filteredParticipants = (meeting.participants || []).filter(
      p => p.user && p.user.id === me.id
    );

    return this.transformResponse({ ...meeting, participants: filteredParticipants });
  },

  async addParticipant(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const { id } = ctx.params;
    const { userId, headsetId } = ctx.request.body;

    if (!userId || !headsetId) {
      return ctx.badRequest('userId and headsetId are required');
    }

    const me = ctx.state.user.appUser;
    const meeting = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    if (!meeting) return ctx.notFound('Meeting not found');

    if (!isManager(ctx) && !(meeting.host && meeting.host.id === me.id)) {
      return ctx.forbidden('Only host or manager can add participants');
    }

    const headset = await strapi.entityService.findOne('api::vr-headset.vr-headset', headsetId, {
      populate: { machine: true },
    });

    if (!headset) return ctx.notFound('Headset not found');
    if (headset.status !== 'idle') {
      return ctx.badRequest('Headset is not idle');
    }
    if (!headset.machine) {
      return ctx.badRequest('Headset has no bound machine');
    }

    if (!isManager(ctx)) {
      const visibleIds = await getVisibleUserIds(strapi, meeting.host.id);
      if (!visibleIds.includes(userId)) {
        return ctx.forbidden('User is not visible to the host');
      }
    }

    const existingParticipation = await strapi.entityService.findMany('api::meeting-participant.meeting-participant', {
      filters: { user: userId, status: { $in: ['invited', 'joined'] } },
      populate: { meeting: true },
    });
    const inActive = existingParticipation.find(p => p.meeting && p.meeting.status === 'active');
    if (inActive) {
      return ctx.badRequest('User is already in another active meeting');
    }

    const participantMachine = headset.machine;
    const hostMachine = meeting.hostMachine;

    const participant = await strapi.entityService.create('api::meeting-participant.meeting-participant', {
      data: {
        meeting: id,
        user: userId,
        headset: headsetId,
        machine: participantMachine.id,
        status: 'invited',
        micEnabled: true,
        vrModeEnabled: false,
      },
    });

    await strapi.entityService.update('api::vr-headset.vr-headset', headsetId, {
      data: { status: 'in-use' },
    });

    try {
      await launchProjectOnMachine(strapi, participantMachine.id, meeting.project.id);
    } catch (e) {
      console.error('[meeting] launchProjectOnMachine failed for participant:', e);
    }

    const hostIp = hostMachine.ip;
    const participantUser = await strapi.entityService.findOne('api::app-user.app-user', userId);
    const participantName = participantUser?.displayName || participantUser?.username || 'Participant';

    try {
      await joinVredSession(participantMachine.ip, participantMachine.port || 8888, hostIp, participantName);
    } catch (e) {
      console.error('[meeting] participant joinVredSession failed:', e);
    }

    await strapi.entityService.update('api::meeting-participant.meeting-participant', participant.id, {
      data: { status: 'joined', joinedAt: new Date() },
    });

    const refreshed = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    return this.transformResponse(refreshed);
  },

  async removeParticipant(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const { id, pid } = ctx.params;
    const me = ctx.state.user.appUser;

    const meeting = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    if (!meeting) return ctx.notFound('Meeting not found');

    if (!isManager(ctx) && !(meeting.host && meeting.host.id === me.id)) {
      return ctx.forbidden('Only host or manager can remove participants');
    }

    const participant = await strapi.entityService.findOne('api::meeting-participant.meeting-participant', pid, {
      populate: POPULATE_PARTICIPANT,
    });

    if (!participant || !participant.meeting || participant.meeting.id !== meeting.id) {
      return ctx.notFound('Participant not found in this meeting');
    }

    if (participant.machine) {
      try {
        await leaveVredSession(participant.machine.ip, participant.machine.port || 8888);
      } catch (e) {
        console.error('[meeting] leaveVredSession failed:', e);
      }

      try {
        await killProcessOnMachine(strapi, participant.machine.id);
      } catch (e) {
        console.error('[meeting] killProcessOnMachine failed:', e);
      }
    }

    if (participant.headset) {
      await strapi.entityService.update('api::vr-headset.vr-headset', participant.headset.id, {
        data: { status: 'idle' },
      });
    }

    await strapi.entityService.update('api::meeting-participant.meeting-participant', pid, {
      data: { status: 'left', leftAt: new Date() },
    });

    const refreshed = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    return this.transformResponse(refreshed);
  },

  async updateParticipant(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const { id, pid } = ctx.params;
    const { action, micEnabled, vrModeEnabled } = ctx.request.body;
    const me = ctx.state.user.appUser;

    const meeting = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    if (!meeting) return ctx.notFound('Meeting not found');

    const participant = await strapi.entityService.findOne('api::meeting-participant.meeting-participant', pid, {
      populate: POPULATE_PARTICIPANT,
    });

    if (!participant || !participant.meeting || participant.meeting.id !== meeting.id) {
      return ctx.notFound('Participant not found in this meeting');
    }

    const canUpdate = isManager(ctx)
      || (meeting.host && meeting.host.id === me.id)
      || (participant.user && participant.user.id === me.id);

    if (!canUpdate) {
      return ctx.forbidden('Not authorized to update this participant');
    }

    if (action === 'join' && participant.machine) {
      const hostMachine = meeting.hostMachine;
      const hostIp = hostMachine.ip;
      const participantUser = participant.user;
      const participantName = participantUser?.displayName || participantUser?.username || 'Participant';
      try {
        await joinVredSession(participant.machine.ip, participant.machine.port || 8888, hostIp, participantName);
      } catch (e) {
        console.error('[meeting] updateParticipant join failed:', e);
      }
      await strapi.entityService.update('api::meeting-participant.meeting-participant', pid, {
        data: { status: 'joined', joinedAt: new Date() },
      });
    }

    if (action === 'leave' && participant.machine) {
      try {
        await leaveVredSession(participant.machine.ip, participant.machine.port || 8888);
      } catch (e) {
        console.error('[meeting] updateParticipant leave failed:', e);
      }
      await strapi.entityService.update('api::meeting-participant.meeting-participant', pid, {
        data: { status: 'left', leftAt: new Date() },
      });
    }

    if (micEnabled !== undefined && participant.machine) {
      try {
        await setMicEnabled(participant.machine.ip, participant.machine.port || 8888, micEnabled);
      } catch (e) {
        console.error('[meeting] updateParticipant setMicEnabled failed:', e);
      }
      await strapi.entityService.update('api::meeting-participant.meeting-participant', pid, {
        data: { micEnabled },
      });
    }

    if (vrModeEnabled !== undefined && participant.machine) {
      try {
        await setVrMode(participant.machine.ip, participant.machine.port || 8888, vrModeEnabled);
      } catch (e) {
        console.error('[meeting] updateParticipant setVrMode failed:', e);
      }
      await strapi.entityService.update('api::meeting-participant.meeting-participant', pid, {
        data: { vrModeEnabled },
      });
    }

    const refreshed = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    return this.transformResponse(refreshed);
  },

  async end(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const { id } = ctx.params;
    const me = ctx.state.user.appUser;

    const meeting = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    if (!meeting) return ctx.notFound('Meeting not found');

    if (!isManager(ctx) && !(meeting.host && meeting.host.id === me.id)) {
      return ctx.forbidden('Only host or manager can end a meeting');
    }

    const participants = meeting.participants || [];

    for (const p of participants) {
      if (p.status === 'joined' && p.machine) {
        try {
          await leaveVredSession(p.machine.ip, p.machine.port || 8888);
        } catch (e) {
          console.error(`[meeting] end: leaveVredSession failed for participant ${p.id}:`, e);
        }
      }
    }

    for (const p of participants) {
      if (p.machine) {
        try {
          await killProcessOnMachine(strapi, p.machine.id);
        } catch (e) {
          console.error(`[meeting] end: killProcessOnMachine failed for participant ${p.id}:`, e);
        }
      }
    }

    for (const p of participants) {
      if (p.headset) {
        await strapi.entityService.update('api::vr-headset.vr-headset', p.headset.id, {
          data: { status: 'idle' },
        });
      }
    }

    await Promise.all(participants.map(p =>
      strapi.entityService.update('api::meeting-participant.meeting-participant', p.id, {
        data: { status: 'left', leftAt: new Date() },
      })
    ));

    try {
      await killProcessOnMachine(strapi, meeting.hostMachine.id);
    } catch (e) {
      console.error('[meeting] end: killProcessOnMachine failed for host machine:', e);
    }

    await strapi.entityService.update('api::meeting.meeting', id, {
      data: { status: 'ended', endedAt: new Date() },
    });

    const refreshed = await strapi.entityService.findOne('api::meeting.meeting', id, {
      populate: POPULATE_MEETING,
    });

    return this.transformResponse(refreshed);
  },

  async visibleUsers(ctx) {
    const authErr = requireAuthenticated(ctx);
    if (authErr) return authErr;

    const me = ctx.state.user.appUser;

    if (isManager(ctx)) {
      const allUsers = await strapi.entityService.findMany('api::app-user.app-user', {
        populate: { appRole: true, projectGroups: true },
      });
      return ctx.send({ data: allUsers });
    }

    const visibleIds = await getVisibleUserIds(strapi, me.id);
    const users = await strapi.entityService.findMany('api::app-user.app-user', {
      filters: { id: { $in: visibleIds } },
      populate: { appRole: true, projectGroups: true },
    });

    return ctx.send({ data: users });
  },

}));
