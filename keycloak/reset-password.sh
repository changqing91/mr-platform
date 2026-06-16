#!/usr/bin/env bash
# Reset the password of any user inside the whattech realm.
#
# Usage:
#   ./keycloak/reset-password.sh                          # resets platformadmin -> Password123!
#   ./keycloak/reset-password.sh alice NewPass!23         # resets a specific user
#   ./keycloak/reset-password.sh alice NewPass!23 true    # third arg=true => one-time, must change at next login
set -euo pipefail

USERNAME=${1:-platformadmin}
PASSWORD=${2:-Password123!}
TEMPORARY=${3:-false}

KC_BOOTSTRAP_ADMIN=${KC_BOOTSTRAP_ADMIN:-admin}
KC_BOOTSTRAP_ADMIN_PASSWORD=${KC_BOOTSTRAP_ADMIN_PASSWORD:-admin}
REALM=${KC_REALM:-whattech}

KCADM="docker exec keycloak /opt/keycloak/bin/kcadm.sh"

echo "[reset] login to master realm..."
$KCADM config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user "$KC_BOOTSTRAP_ADMIN" \
  --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null

echo "[reset] resolving user id for '$USERNAME'..."
USER_ID=$($KCADM get users -r "$REALM" -q "username=$USERNAME" -q "exact=true" --format json 2>/dev/null \
  | node -e "
let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{
  try { const a=JSON.parse(s); if(Array.isArray(a)&&a[0]) process.stdout.write(a[0].id||''); } catch(e){}
});")

if [ -z "$USER_ID" ]; then
  echo "[error] user '$USERNAME' not found in realm '$REALM'" >&2
  exit 1
fi

echo "[reset] user id = $USER_ID"

# Clear required-actions and ensure the user is enabled so login isn't blocked.
$KCADM update "users/$USER_ID" -r "$REALM" \
  -s "enabled=true" \
  -s "emailVerified=true" \
  -s 'requiredActions=[]' >/dev/null 2>&1 || true

echo "[reset] setting password (temporary=$TEMPORARY)..."
if [ "$TEMPORARY" = "true" ]; then
  $KCADM set-password -r "$REALM" --userid "$USER_ID" --new-password "$PASSWORD" --temporary
else
  $KCADM set-password -r "$REALM" --userid "$USER_ID" --new-password "$PASSWORD"
fi

echo "[ok] password reset for '$USERNAME'."
