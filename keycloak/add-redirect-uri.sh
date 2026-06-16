#!/usr/bin/env bash
# Append a redirect URI to the mr-platform-web client.
#
# Usage:
#   ./keycloak/add-redirect-uri.sh "https://your-host:5173/*"
#   ./keycloak/add-redirect-uri.sh "http://192.168.7.80/*"
#
# Multiple URIs can be supplied as separate args.
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <redirect-uri> [<redirect-uri> ...]" >&2
  exit 1
fi

KC_BOOTSTRAP_ADMIN=${KC_BOOTSTRAP_ADMIN:-admin}
KC_BOOTSTRAP_ADMIN_PASSWORD=${KC_BOOTSTRAP_ADMIN_PASSWORD:-admin}
REALM=${KC_REALM:-whattech}
WEB_CLIENT_ID=${KC_WEB_CLIENT_ID:-mr-platform-web}

KCADM="docker exec keycloak /opt/keycloak/bin/kcadm.sh"

$KCADM config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user "$KC_BOOTSTRAP_ADMIN" \
  --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null

WEB_ID=$($KCADM get clients -r "$REALM" -q clientId="$WEB_CLIENT_ID" --fields id 2>/dev/null \
  | node -e "
let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{
  try { const a=JSON.parse(s); if(Array.isArray(a)&&a[0]) process.stdout.write(a[0].id||''); } catch(e){}
});")
if [ -z "$WEB_ID" ]; then
  echo "[error] client '$WEB_CLIENT_ID' not found in realm '$REALM'" >&2
  exit 1
fi

# Pull current redirectUris JSON array
CURRENT=$($KCADM get "clients/$WEB_ID" -r "$REALM" --fields redirectUris --format json 2>/dev/null \
  | sed -n 's/.*"redirectUris" *: *\(\[[^]]*\]\).*/\1/p')
if [ -z "$CURRENT" ]; then
  CURRENT='[]'
fi

# Build merged JSON array (dedupe)
MERGED=$(node -e "
const cur = JSON.parse(process.argv[1]);
const adds = process.argv.slice(2);
const set = new Set([...cur, ...adds]);
process.stdout.write(JSON.stringify([...set]));
" "$CURRENT" "$@")

echo "[info] new redirectUris = $MERGED"
$KCADM update "clients/$WEB_ID" -r "$REALM" -s "redirectUris=$MERGED"
echo "[ok] updated."
