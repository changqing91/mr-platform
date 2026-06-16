'use strict';

/**
 * Keycloak integration config (env-driven).
 *
 * KEYCLOAK_BASE_URL          e.g. http://keycloak:8080
 * KEYCLOAK_REALM             e.g. whattech
 * KEYCLOAK_WEB_CLIENT_ID     SPA client id, used as expected `azp`/`aud`
 * KEYCLOAK_ADMIN_CLIENT_ID   confidential client id (service account)
 * KEYCLOAK_ADMIN_CLIENT_SECRET
 * KEYCLOAK_DISABLED          set to 'true' to bypass auth (dev only)
 */
module.exports = ({ env }) => {
  const baseUrl = env('KEYCLOAK_BASE_URL', 'http://keycloak:8080').replace(/\/$/, '');
  const realm = env('KEYCLOAK_REALM', 'whattech');
  const issuer = `${baseUrl}/realms/${realm}`;

  return {
    enabled: env.bool('KEYCLOAK_DISABLED', false) === false,
    baseUrl,
    realm,
    issuer,
    jwksUri: `${issuer}/protocol/openid-connect/certs`,
    webClientId: env('KEYCLOAK_WEB_CLIENT_ID', 'mr-platform-web'),
    admin: {
      clientId: env('KEYCLOAK_ADMIN_CLIENT_ID', 'mr-platform-admin'),
      clientSecret: env('KEYCLOAK_ADMIN_CLIENT_SECRET', ''),
    },
    // Realm role that grants cross-system platform admin
    platformAdminRole: env('KEYCLOAK_PLATFORM_ADMIN_ROLE', 'platform-admin'),
  };
};
