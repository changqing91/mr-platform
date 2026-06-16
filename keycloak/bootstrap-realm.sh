#!/usr/bin/env bash
# Bootstrap the `whattech` realm: creates realm, clients, roles, and an initial
# platform-admin user. Idempotent (safe to re-run).
set -euo pipefail

KC_BASE_URL=${KC_BASE_URL:-http://localhost:8080}
KC_BOOTSTRAP_ADMIN=${KC_BOOTSTRAP_ADMIN:-admin}
KC_BOOTSTRAP_ADMIN_PASSWORD=${KC_BOOTSTRAP_ADMIN_PASSWORD:-admin}
REALM=${KC_REALM:-whattech}

# Public SPA client (frontend)
WEB_CLIENT_ID=${KC_WEB_CLIENT_ID:-mr-platform-web}
WEB_REDIRECT_URIS=${KC_WEB_REDIRECT_URIS:-"http://localhost:5173/*,https://localhost:5173/*,http://localhost/*,https://localhost/*,http://localhost:80/*,https://localhost:443/*,http://127.0.0.1:5173/*,https://127.0.0.1:5173/*"}
WEB_WEB_ORIGINS=${KC_WEB_WEB_ORIGINS:-"+"}

# Confidential admin client (backend service-account)
ADMIN_CLIENT_ID=${KC_ADMIN_CLIENT_ID:-mr-platform-admin}
ADMIN_CLIENT_SECRET=${KC_ADMIN_CLIENT_SECRET:-mr-platform-admin-secret-change-me}

# Initial platform admin (mr-platform manager)
PLATFORM_ADMIN_USERNAME=${KC_PLATFORM_ADMIN_USERNAME:-platformadmin}
PLATFORM_ADMIN_PASSWORD=${KC_PLATFORM_ADMIN_PASSWORD:-Password123!}
PLATFORM_ADMIN_EMAIL=${KC_PLATFORM_ADMIN_EMAIL:-platformadmin@what-tech.cn}

KCADM="docker exec keycloak /opt/keycloak/bin/kcadm.sh"

# Robust id lookup: parse JSON output (kcadm CSV behavior varies across versions
# and sometimes omits the header line, breaking `tail -n +2`).
json_first_id() {
  node -e "
let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{
  try { const a=JSON.parse(s); if(Array.isArray(a)&&a[0]) process.stdout.write(a[0].id||''); } catch(e){}
});"
}

get_client_id() {
  $KCADM get clients -r "$REALM" -q "clientId=$1" --fields id 2>/dev/null | json_first_id
}

resolve_user_id() {
  $KCADM get users -r "$REALM" -q "username=$1" -q "exact=true" --format json 2>/dev/null | json_first_id
}

get_service_account_user_id() {
  $KCADM get "clients/$1/service-account-user" -r "$REALM" --fields id 2>/dev/null \
    | node -e "
let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{
  try { const o=JSON.parse(s); process.stdout.write((o&&o.id)||''); } catch(e){}
});"
}

echo "[bootstrap] login to master realm..."
$KCADM config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user "$KC_BOOTSTRAP_ADMIN" \
  --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null

# ---------- Realm ----------
if $KCADM get "realms/$REALM" >/dev/null 2>&1; then
  echo "[bootstrap] realm '$REALM' already exists"
else
  echo "[bootstrap] creating realm '$REALM'..."
  $KCADM create realms -s realm="$REALM" -s enabled=true -s registrationAllowed=false
fi

# ---------- Realm Roles ----------
ensure_realm_role() {
  local role=$1
  if $KCADM get "roles/$role" -r "$REALM" >/dev/null 2>&1; then
    echo "[bootstrap] role '$role' exists"
  else
    echo "[bootstrap] creating realm role '$role'..."
    $KCADM create roles -r "$REALM" -s name="$role"
  fi
}
ensure_realm_role platform-admin

# ---------- Web (SPA) Client ----------
WEB_ID=$(get_client_id "$WEB_CLIENT_ID")

# Convert comma-separated redirect URIs into a JSON array
to_json_array() {
  local IFS=','
  local arr=( $1 )
  local first=1
  printf '['
  for s in "${arr[@]}"; do
    if [ "$first" -eq 1 ]; then first=0; else printf ','; fi
    printf '"%s"' "$s"
  done
  printf ']'
}
REDIRECT_JSON=$(to_json_array "$WEB_REDIRECT_URIS")
ORIGINS_JSON=$(to_json_array "$WEB_WEB_ORIGINS")

if [ -z "$WEB_ID" ]; then
  echo "[bootstrap] creating web client '$WEB_CLIENT_ID'..."
  $KCADM create clients -r "$REALM" \
    -s "clientId=$WEB_CLIENT_ID" \
    -s "publicClient=true" \
    -s "standardFlowEnabled=true" \
    -s "directAccessGrantsEnabled=false" \
    -s "implicitFlowEnabled=false" \
    -s "serviceAccountsEnabled=false" \
    -s "redirectUris=$REDIRECT_JSON" \
    -s "webOrigins=$ORIGINS_JSON" \
    -s "attributes.\"pkce.code.challenge.method\"=S256" \
    -s "attributes.\"post.logout.redirect.uris\"=+"
  WEB_ID=$(get_client_id "$WEB_CLIENT_ID")
else
  echo "[bootstrap] web client '$WEB_CLIENT_ID' exists ($WEB_ID), updating..."
  $KCADM update "clients/$WEB_ID" -r "$REALM" \
    -s "publicClient=true" \
    -s "standardFlowEnabled=true" \
    -s "directAccessGrantsEnabled=false" \
    -s "implicitFlowEnabled=false" \
    -s "serviceAccountsEnabled=false" \
    -s "redirectUris=$REDIRECT_JSON" \
    -s "webOrigins=$ORIGINS_JSON" \
    -s "attributes.\"pkce.code.challenge.method\"=S256" \
    -s "attributes.\"post.logout.redirect.uris\"=+"
fi

# ---------- Admin (service-account) Client ----------
ADMIN_ID=$(get_client_id "$ADMIN_CLIENT_ID")

if [ -z "$ADMIN_ID" ]; then
  echo "[bootstrap] creating admin client '$ADMIN_CLIENT_ID'..."
  $KCADM create clients -r "$REALM" \
    -s "clientId=$ADMIN_CLIENT_ID" \
    -s "publicClient=false" \
    -s "standardFlowEnabled=false" \
    -s "directAccessGrantsEnabled=false" \
    -s "serviceAccountsEnabled=true" \
    -s "secret=$ADMIN_CLIENT_SECRET"
  ADMIN_ID=$(get_client_id "$ADMIN_CLIENT_ID")
else
  echo "[bootstrap] admin client '$ADMIN_CLIENT_ID' exists ($ADMIN_ID), updating..."
  $KCADM update "clients/$ADMIN_ID" -r "$REALM" \
    -s "publicClient=false" \
    -s "standardFlowEnabled=false" \
    -s "directAccessGrantsEnabled=false" \
    -s "serviceAccountsEnabled=true" \
    -s "secret=$ADMIN_CLIENT_SECRET"
fi

# ---------- Grant realm-management roles to the admin client's service account ----------
echo "[bootstrap] granting realm-management roles to '$ADMIN_CLIENT_ID' service account..."
SA_USER_ID=$(get_service_account_user_id "$ADMIN_ID")

# realm-management is a built-in client; find its id
RM_CLIENT_ID=$(get_client_id "realm-management")

for role in manage-users view-users query-users query-groups; do
  $KCADM add-roles -r "$REALM" \
    --uid "$SA_USER_ID" \
    --cclientid realm-management \
    --rolename "$role" >/dev/null 2>&1 || echo "  (role $role already assigned or unavailable)"
done

# ---------- Initial platform-admin user ----------
USER_ID=$(resolve_user_id "$PLATFORM_ADMIN_USERNAME")

if [ -n "$USER_ID" ]; then
  echo "[bootstrap] platform admin user '$PLATFORM_ADMIN_USERNAME' already exists ($USER_ID)"
else
  echo "[bootstrap] creating platform admin user '$PLATFORM_ADMIN_USERNAME'..."
  $KCADM create users -r "$REALM" \
    -s "username=$PLATFORM_ADMIN_USERNAME" \
    -s "email=$PLATFORM_ADMIN_EMAIL" \
    -s "firstName=Platform" \
    -s "lastName=Admin" \
    -s "enabled=true" \
    -s "emailVerified=true"
  USER_ID=$(resolve_user_id "$PLATFORM_ADMIN_USERNAME")
fi

if [ -z "$USER_ID" ]; then
  echo "[error] failed to resolve user id for '$PLATFORM_ADMIN_USERNAME'" >&2
  exit 1
fi

# Always (re)set the password to the configured value, non-temporary, so the
# initial credentials are guaranteed to work even if a previous bootstrap was
# interrupted between user-create and set-password.
echo "[bootstrap] (re)setting password for '$PLATFORM_ADMIN_USERNAME'..."
$KCADM set-password -r "$REALM" --userid "$USER_ID" --new-password "$PLATFORM_ADMIN_PASSWORD"

# Make sure the user is enabled and required-actions are clear (no forced
# password change at first login for the bootstrap admin).
$KCADM update "users/$USER_ID" -r "$REALM" \
  -s "enabled=true" \
  -s "emailVerified=true" \
  -s 'requiredActions=[]' >/dev/null 2>&1 || true

echo "[bootstrap] assigning 'platform-admin' realm role to '$PLATFORM_ADMIN_USERNAME'..."
$KCADM add-roles -r "$REALM" --uusername "$PLATFORM_ADMIN_USERNAME" --rolename platform-admin >/dev/null 2>&1 || true

cat <<EOF

[bootstrap] done.

  Realm:               $REALM
  Issuer:              $KC_BASE_URL/realms/$REALM
  Web client (SPA):    $WEB_CLIENT_ID
  Admin client:        $ADMIN_CLIENT_ID
  Admin client secret: $ADMIN_CLIENT_SECRET
  Initial admin user:  $PLATFORM_ADMIN_USERNAME / $PLATFORM_ADMIN_PASSWORD
EOF
