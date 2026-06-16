'use strict';

/**
 * Wrapper around @keycloak/keycloak-admin-client.
 * Lazily authenticates with the configured service-account client and refreshes
 * the token on demand.
 */

let kcAdmin = null;
let lastAuthAt = 0;
const AUTH_TTL_MS = 50 * 1000; // re-auth roughly every minute

const getConfig = () => strapi.config.get('keycloak');

const ensureClient = async () => {
  const cfg = getConfig();
  if (!cfg || cfg.enabled === false) {
    throw new Error('Keycloak integration is disabled');
  }
  if (!cfg.admin?.clientSecret) {
    throw new Error('KEYCLOAK_ADMIN_CLIENT_SECRET is not configured');
  }

  if (!kcAdmin) {
    const { default: KcAdminClient } = await import('@keycloak/keycloak-admin-client');
    kcAdmin = new KcAdminClient({
      baseUrl: cfg.baseUrl,
      realmName: cfg.realm,
    });
  }

  const now = Date.now();
  if (now - lastAuthAt > AUTH_TTL_MS) {
    await kcAdmin.auth({
      grantType: 'client_credentials',
      clientId: cfg.admin.clientId,
      clientSecret: cfg.admin.clientSecret,
    });
    lastAuthAt = now;
  }
  kcAdmin.setConfig({ realmName: cfg.realm });
  return kcAdmin;
};

module.exports = {
  /**
   * Create a new Keycloak user and (optionally) set an initial password.
   * Returns the Keycloak user `sub` (id).
   */
  async createUser({ username, email, displayName, password, temporary = true }) {
    const client = await ensureClient();
    const [firstName, ...rest] = (displayName || username || '').split(' ');
    const lastName = rest.join(' ') || '';

    const created = await client.users.create({
      username,
      email: email || undefined,
      firstName: firstName || username,
      lastName,
      enabled: true,
      emailVerified: true,
    });

    if (password) {
      await client.users.resetPassword({
        id: created.id,
        credential: {
          type: 'password',
          value: password,
          temporary,
        },
      });
    }

    return created.id;
  },

  async updateUser(sub, { username, email, displayName, enabled }) {
    const client = await ensureClient();
    const payload = {};
    if (username !== undefined) payload.username = username;
    if (email !== undefined) payload.email = email;
    if (enabled !== undefined) payload.enabled = enabled;
    if (displayName !== undefined) {
      const [first, ...rest] = displayName.split(' ');
      payload.firstName = first || displayName;
      payload.lastName = rest.join(' ') || '';
    }
    if (Object.keys(payload).length > 0) {
      await client.users.update({ id: sub }, payload);
    }
  },

  async deleteUser(sub) {
    const client = await ensureClient();
    await client.users.del({ id: sub });
  },

  async resetPassword(sub, password, temporary = true) {
    const client = await ensureClient();
    await client.users.resetPassword({
      id: sub,
      credential: { type: 'password', value: password, temporary },
    });
  },

  async findUserByUsername(username) {
    const client = await ensureClient();
    const list = await client.users.find({ username, exact: true });
    return list?.[0] || null;
  },
};
