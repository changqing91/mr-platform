'use strict';

const { createCoreController } = require('@strapi/strapi').factories;
const { requireAuthenticated, requireManager, isManager, isPlatformAdmin } = require('../../../utils/auth');
const keycloakAdmin = require('../../../services/keycloak-admin');

const POPULATE = {
  appRole: true,
  projectGroups: true,
};

module.exports = createCoreController('api::app-user.app-user', ({ strapi }) => ({
  /** GET /api/me - returns current user's full profile (auth required, any role). */
  async me(ctx) {
    if (requireAuthenticated(ctx)) return;
    const u = ctx.state.user;
    let appUser = u.appUser;
    if (appUser?.id) {
      appUser = await strapi.entityService.findOne('api::app-user.app-user', appUser.id, {
        populate: POPULATE,
      });
    }
    ctx.body = {
      data: {
        kcSub: u.kcSub,
        username: u.username,
        email: u.email,
        displayName: u.displayName,
        realmRoles: u.realmRoles,
        isManager: isManager(ctx),
        isPlatformAdmin: isPlatformAdmin(ctx),
        appUser,
      },
    };
  },

  async find(ctx) {
    if (requireManager(ctx)) return;
    const list = await strapi.entityService.findMany('api::app-user.app-user', {
      sort: { createdAt: 'asc' },
      populate: POPULATE,
    });
    ctx.body = { data: list };
  },

  async findOne(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const entry = await strapi.entityService.findOne('api::app-user.app-user', id, {
      populate: POPULATE,
    });
    if (!entry) return ctx.notFound();
    ctx.body = { data: entry };
  },

  /**
   * POST /api/app-users
   * Body: { username, email, password, displayName, appRoleId, projectGroupIds: [] }
   * Creates user in Keycloak and mirrors locally.
   */
  async create(ctx) {
    if (requireManager(ctx)) return;
    const data = ctx.request.body?.data || ctx.request.body || {};
    const username = (data.username || '').trim();
    const email = (data.email || '').trim() || null;
    const password = (data.password || '').trim();
    const displayName = (data.displayName || username).trim();
    const appRoleId = data.appRoleId || null;
    const projectGroupIds = Array.isArray(data.projectGroupIds) ? data.projectGroupIds : [];

    if (!username) return ctx.badRequest('用户名必填');
    if (!password || password.length < 6) return ctx.badRequest('初始密码至少 6 位');

    // Validate appRole if provided
    if (appRoleId) {
      const role = await strapi.entityService.findOne('api::app-role.app-role', appRoleId);
      if (!role) return ctx.badRequest('指定的角色不存在');
    }

    let kcSub = null;
    try {
      kcSub = await keycloakAdmin.createUser({
        username,
        email,
        displayName,
        password,
        temporary: !!data.temporaryPassword,
      });
    } catch (err) {
      strapi.log.error('[app-user.create] Keycloak createUser failed', err);
      const message = err?.responseData?.errorMessage || err.message || '创建 Keycloak 用户失败';
      return ctx.badRequest(message);
    }

    let created;
    try {
      created = await strapi.entityService.create('api::app-user.app-user', {
        data: {
          keycloakId: kcSub,
          username,
          email,
          displayName,
          appRole: appRoleId || null,
          projectGroups: projectGroupIds,
          lastSyncAt: new Date().toISOString(),
        },
        populate: POPULATE,
      });
    } catch (err) {
      // rollback Keycloak side on local failure
      try { await keycloakAdmin.deleteUser(kcSub); } catch (_) { /* ignore */ }
      strapi.log.error('[app-user.create] local create failed, rolled back Keycloak', err);
      return ctx.badRequest('创建本地用户失败');
    }

    ctx.body = { data: created };
  },

  /**
   * PUT /api/app-users/:id
   * Body: { displayName?, email?, appRoleId?, projectGroupIds? }
   */
  async update(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const data = ctx.request.body?.data || ctx.request.body || {};

    const target = await strapi.entityService.findOne('api::app-user.app-user', id, { populate: POPULATE });
    if (!target) return ctx.notFound();

    const patch = {};
    const kcPatch = {};

    if (typeof data.displayName === 'string' && data.displayName.trim()) {
      patch.displayName = data.displayName.trim();
      kcPatch.displayName = data.displayName.trim();
    }
    if (typeof data.email === 'string') {
      patch.email = data.email.trim() || null;
      kcPatch.email = data.email.trim() || null;
    }
    if (data.appRoleId !== undefined) {
      if (data.appRoleId) {
        const role = await strapi.entityService.findOne('api::app-role.app-role', data.appRoleId);
        if (!role) return ctx.badRequest('指定的角色不存在');
      }
      patch.appRole = data.appRoleId || null;
    }
    if (Array.isArray(data.projectGroupIds)) {
      patch.projectGroups = data.projectGroupIds;
    }

    if (Object.keys(kcPatch).length > 0 && target.keycloakId) {
      try {
        await keycloakAdmin.updateUser(target.keycloakId, kcPatch);
      } catch (err) {
        strapi.log.warn('[app-user.update] Keycloak update failed', err);
        // continue with local update; Keycloak side may be slightly out-of-sync
      }
    }

    const updated = await strapi.entityService.update('api::app-user.app-user', id, {
      data: patch,
      populate: POPULATE,
    });
    ctx.body = { data: updated };
  },

  /**
   * DELETE /api/app-users/:id - removes locally and on Keycloak.
   */
  async delete(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const target = await strapi.entityService.findOne('api::app-user.app-user', id);
    if (!target) return ctx.notFound();

    if (ctx.state.user.appUser?.id === target.id) {
      return ctx.badRequest('不能删除自己');
    }

    if (target.keycloakId) {
      try { await keycloakAdmin.deleteUser(target.keycloakId); }
      catch (err) {
        strapi.log.warn('[app-user.delete] Keycloak delete failed (continuing)', err);
      }
    }
    await strapi.entityService.delete('api::app-user.app-user', id);
    ctx.body = { data: { id } };
  },

  /**
   * PUT /api/app-users/:id/password - reset by admin (temporary=true → user must change next login).
   */
  async resetPassword(ctx) {
    if (requireManager(ctx)) return;
    const { id } = ctx.params;
    const { password, temporary = true } = ctx.request.body || {};
    if (!password || password.length < 6) return ctx.badRequest('密码至少 6 位');

    const target = await strapi.entityService.findOne('api::app-user.app-user', id);
    if (!target || !target.keycloakId) return ctx.notFound();

    try {
      await keycloakAdmin.resetPassword(target.keycloakId, password, !!temporary);
    } catch (err) {
      strapi.log.error('[app-user.resetPassword] failed', err);
      return ctx.badRequest('重置密码失败');
    }
    ctx.body = { message: '密码已更新' };
  },
}));
