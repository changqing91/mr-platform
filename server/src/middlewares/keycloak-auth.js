'use strict';

/**
 * keycloak-auth - 全局认证中间件
 *
 * - 校验 Authorization: Bearer <access_token>
 * - 用 Keycloak JWKS 验签
 * - 校验 iss / exp
 * - 提取 claims 并按 sub upsert 本地 app-user
 * - 把当前用户写入 ctx.state.user
 *
 * 白名单路径：
 *   - 非 /api/* (admin 面板等)
 *   - /api/license/*
 *   - /api/health (如有)
 */

const { createRemoteJWKSet, jwtVerify } = require('jose');

const PUBLIC_PATHS = [
  /^\/api\/license(\/|$)/,
  /^\/api\/health$/,
];

let cachedJwks = null;
let cachedJwksUri = null;

const getJwks = (jwksUri) => {
  if (!cachedJwks || cachedJwksUri !== jwksUri) {
    cachedJwks = createRemoteJWKSet(new URL(jwksUri), {
      cooldownDuration: 30_000,
      cacheMaxAge: 10 * 60_000,
    });
    cachedJwksUri = jwksUri;
  }
  return cachedJwks;
};

const isPublicPath = (path) => {
  if (!path.startsWith('/api/')) return true;
  return PUBLIC_PATHS.some((re) => re.test(path));
};

module.exports = (_config, { strapi }) => {
  return async (ctx, next) => {
    const path = ctx.request.path;

    if (isPublicPath(path) || ctx.method === 'OPTIONS') {
      return next();
    }

    const kc = strapi.config.get('keycloak');
    if (!kc || kc.enabled === false) {
      // Auth bypassed in dev; treat as unauthenticated public access still gated by ACLs
      return next();
    }

    const authHeader = ctx.request.headers.authorization || '';
    const match = authHeader.match(/^Bearer\s+(.+)$/i);
    if (!match) {
      ctx.status = 401;
      ctx.body = { error: 'UNAUTHENTICATED', message: '缺少访问令牌' };
      return;
    }

    const token = match[1];
    let payload;
    try {
      const jwks = getJwks(kc.jwksUri);
      const result = await jwtVerify(token, jwks, {
        issuer: kc.issuer,
        // Keycloak access tokens have `aud` set to clients with audience mappers.
        // We don't enforce aud strictly here (would need extra mapper config); we
        // accept any token issued by the realm and let azp/role checks gate access.
      });
      payload = result.payload;
    } catch (err) {
      strapi.log.warn(`[keycloak-auth] token verify failed: ${err.message}`);
      ctx.status = 401;
      ctx.body = { error: 'INVALID_TOKEN', message: '令牌无效或已过期' };
      return;
    }

    const sub = payload.sub;
    if (!sub) {
      ctx.status = 401;
      ctx.body = { error: 'INVALID_TOKEN', message: '令牌缺少 sub' };
      return;
    }

    const realmRoles = payload.realm_access?.roles || [];
    const claims = {
      sub,
      username: payload.preferred_username || sub,
      email: payload.email || null,
      displayName: payload.name || payload.preferred_username || sub,
      realmRoles,
    };

    // Lazy provisioning: upsert app-user by sub
    let appUser = null;
    try {
      appUser = await strapi.service('api::app-user.app-user').upsertByClaims(claims);
    } catch (err) {
      strapi.log.error('[keycloak-auth] failed to upsert app-user', err);
      ctx.status = 500;
      ctx.body = { error: 'USER_SYNC_FAILED', message: '用户同步失败' };
      return;
    }

    ctx.state.user = {
      kcSub: claims.sub,
      username: claims.username,
      email: claims.email,
      displayName: claims.displayName,
      realmRoles,
      appUser,
    };

    return next();
  };
};
