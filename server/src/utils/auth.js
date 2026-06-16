'use strict';

/**
 * Authorization helpers built around `ctx.state.user` populated by the
 * keycloak-auth middleware.
 */

const isAuthenticated = (ctx) => !!ctx.state.user?.kcSub;

const isPlatformAdmin = (ctx) => {
  const user = ctx.state.user;
  if (!user) return false;
  const platformRole = strapi.config.get('keycloak.platformAdminRole', 'platform-admin');
  return Array.isArray(user.realmRoles) && user.realmRoles.includes(platformRole);
};

const isManager = (ctx) => {
  if (!isAuthenticated(ctx)) return false;
  if (isPlatformAdmin(ctx)) return true;
  const role = ctx.state.user.appUser?.appRole;
  return !!(role && role.canManage === true);
};

const requireAuthenticated = (ctx) => {
  if (!isAuthenticated(ctx)) {
    return ctx.unauthorized('未登录');
  }
  return null;
};

const requireManager = (ctx) => {
  const authErr = requireAuthenticated(ctx);
  if (authErr) return authErr;
  if (!isManager(ctx)) {
    return ctx.forbidden('无管理权限');
  }
  return null;
};

module.exports = {
  isAuthenticated,
  isPlatformAdmin,
  isManager,
  requireAuthenticated,
  requireManager,
};
