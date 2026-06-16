/**
 * OIDC auth service using oidc-client-ts.
 *
 * Configuration is read from Vite env vars:
 *   VITE_OIDC_AUTHORITY      e.g. http://localhost:8080/realms/whattech
 *   VITE_OIDC_CLIENT_ID      e.g. mr-platform-web
 *
 * The SPA uses HashRouter. The redirect URI is the page origin itself; on app
 * boot we detect ?code=&state= in the query string and complete the callback.
 */

import { UserManager, WebStorageStateStore, Log } from 'oidc-client-ts';

const authority = import.meta.env.VITE_OIDC_AUTHORITY || 'http://localhost:8080/realms/whattech';
const clientId  = import.meta.env.VITE_OIDC_CLIENT_ID  || 'mr-platform-web';

if (import.meta.env.DEV) {
  Log.setLogger(console);
  Log.setLevel(Log.WARN);
}

// Use a stable URL without hash for the redirect; Keycloak doesn't allow fragments.
// We strip any hash after callback.
const redirectUri = `${window.location.origin}${window.location.pathname}`;

if (import.meta.env.DEV) {
    // Help configuring Keycloak's Valid redirect URIs.
    // eslint-disable-next-line no-console
    console.info('[oidc] authority    =', authority);
    // eslint-disable-next-line no-console
    console.info('[oidc] client_id    =', clientId);
    // eslint-disable-next-line no-console
    console.info('[oidc] redirect_uri =', redirectUri);
}

export const userManager = new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: redirectUri,
    post_logout_redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid profile email',
    automaticSilentRenew: false,
    loadUserInfo: true,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    monitorSession: false,
});

export const isCallbackUrl = () => {
    const params = new URLSearchParams(window.location.search);
    return params.has('code') && params.has('state');
};

/** Complete an OIDC redirect callback. Returns the User on success.
 *
 * Module-level memoization protects against double-invocation, which happens
 * in two common scenarios:
 *   1. React 18 StrictMode runs effects twice in development, so the bootstrap
 *      effect would call this twice on the same ?code= and the second call
 *      would fail with `invalid_grant: Code not valid`.
 *   2. The user accidentally reloads the page before we have stripped
 *      ?code= from the URL.
 * In both cases we return the in-flight (or completed) result instead of
 * exchanging the code a second time.
 */
let callbackPromise = null;
export const completeCallback = () => {
    if (!callbackPromise) {
        callbackPromise = (async () => {
            const user = await userManager.signinRedirectCallback();
            // Clean ?code=&state= from the URL bar so a refresh won't replay it.
            const cleanUrl = window.location.pathname + (window.location.hash || '');
            window.history.replaceState({}, document.title, cleanUrl);
            return user;
        })();
    }
    return callbackPromise;
};

export const login = (state) => userManager.signinRedirect({ state });

export const logout = async () => {
    try {
        await userManager.signoutRedirect();
    } catch (_) {
        await userManager.removeUser();
        window.location.href = '/';
    }
};

export const getUser = () => userManager.getUser();

export const getAccessToken = async () => {
    const user = await userManager.getUser();
    if (!user || user.expired) return null;
    return user.access_token;
};

userManager.events.addAccessTokenExpired(() => {
    userManager.signinSilent().catch(() => {
        userManager.removeUser();
    });
});
