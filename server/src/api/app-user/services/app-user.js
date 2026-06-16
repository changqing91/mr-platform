'use strict';

const { createCoreService } = require('@strapi/strapi').factories;

const POPULATE = {
  appRole: true,
  projectGroups: true,
};

module.exports = createCoreService('api::app-user.app-user', ({ strapi }) => ({
  /**
   * Find by Keycloak sub with role/groups populated.
   */
  async findByKeycloakId(sub) {
    const list = await strapi.entityService.findMany('api::app-user.app-user', {
      filters: { keycloakId: sub },
      populate: POPULATE,
      limit: 1,
    });
    return list && list[0] ? list[0] : null;
  },

  /**
   * Lazy-provisioning: ensure a local app-user exists for the given Keycloak
   * claims. Cached fields (username/email/displayName) are refreshed.
   *
   * If a Keycloak user is deleted and recreated with the same username, its
   * `sub` changes. To avoid leaving an orphan local row whose `keycloakId`
   * points to a non-existent KC user, we re-key any matching-username row to
   * the new sub instead of inserting a duplicate.
   */
  async upsertByClaims(claims) {
    const existing = await this.findByKeycloakId(claims.sub);
    const now = new Date().toISOString();

    if (existing) {
      const patch = {};
      if (claims.username && existing.username !== claims.username) patch.username = claims.username;
      if (claims.email && existing.email !== claims.email) patch.email = claims.email;
      if (claims.displayName && existing.displayName !== claims.displayName) patch.displayName = claims.displayName;
      patch.lastSyncAt = now;

      if (Object.keys(patch).length > 0) {
        await strapi.entityService.update('api::app-user.app-user', existing.id, {
          data: patch,
        });
      }
      return this.findByKeycloakId(claims.sub);
    }

    // No row with this sub. Check whether an old row with the same username
    // exists (typical case: KC user was deleted and recreated). If so, rebind
    // it to the new sub instead of creating a duplicate.
    if (claims.username) {
      const stale = await strapi.entityService.findMany('api::app-user.app-user', {
        filters: { username: claims.username },
        limit: 1,
      });
      if (stale && stale[0]) {
        await strapi.entityService.update('api::app-user.app-user', stale[0].id, {
          data: {
            keycloakId: claims.sub,
            email: claims.email || stale[0].email,
            displayName: claims.displayName || stale[0].displayName,
            lastSyncAt: now,
          },
        });
        return this.findByKeycloakId(claims.sub);
      }
    }

    await strapi.entityService.create('api::app-user.app-user', {
      data: {
        keycloakId: claims.sub,
        username: claims.username,
        email: claims.email,
        displayName: claims.displayName,
        lastSyncAt: now,
      },
    });
    return this.findByKeycloakId(claims.sub);
  },
}));
