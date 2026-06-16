#!/usr/bin/env bash
set -euo pipefail

# Keycloak + Postgres deployment for unified identity (SSO).
# Run after `deploy.sh` (re-uses the same docker network).

ROOT=$(cd "$(dirname "$0")" && pwd)

KEYCLOAK_IMAGE=${KEYCLOAK_IMAGE:-quay.io/keycloak/keycloak:26.0}
KC_POSTGRES_IMAGE=${KC_POSTGRES_IMAGE:-postgres:16}
NETWORK=${NETWORK:-mr-net}
RESTART_POLICY=${RESTART_POLICY:-unless-stopped}

KC_HTTP_PORT=${KC_HTTP_PORT:-8080}
KC_HOSTNAME=${KC_HOSTNAME:-localhost}
KC_HOSTNAME_STRICT=${KC_HOSTNAME_STRICT:-false}
KC_PROXY_HEADERS=${KC_PROXY_HEADERS:-xforwarded}
KC_HTTP_ENABLED=${KC_HTTP_ENABLED:-true}

KC_BOOTSTRAP_ADMIN=${KC_BOOTSTRAP_ADMIN:-admin}
KC_BOOTSTRAP_ADMIN_PASSWORD=${KC_BOOTSTRAP_ADMIN_PASSWORD:-admin}

KC_DB_NAME=${KC_DB_NAME:-keycloak}
KC_DB_USER=${KC_DB_USER:-keycloak}
KC_DB_PASSWORD=${KC_DB_PASSWORD:-keycloak}
KC_DB_VOLUME=${KC_DB_VOLUME:-mr-keycloak-pg}
KC_DB_HOST_DIR=${KC_DB_HOST_DIR:-}

REALM=${KC_REALM:-whattech}

echo "[keycloak] using network: $NETWORK"
docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"

if [ -n "${KC_DB_HOST_DIR}" ]; then
  if ! mkdir -p "$KC_DB_HOST_DIR" >/dev/null 2>&1; then
    KC_DB_HOST_DIR="$ROOT/.data/keycloak-pg"
    mkdir -p "$KC_DB_HOST_DIR"
  fi
  KC_DB_MOUNT="$KC_DB_HOST_DIR:/var/lib/postgresql/data"
else
  docker volume inspect "$KC_DB_VOLUME" >/dev/null 2>&1 || docker volume create "$KC_DB_VOLUME" >/dev/null
  KC_DB_MOUNT="$KC_DB_VOLUME:/var/lib/postgresql/data"
fi

docker rm -f keycloak keycloak-db >/dev/null 2>&1 || true

echo "[keycloak] starting Postgres..."
docker run -d \
  --name keycloak-db \
  --restart "$RESTART_POLICY" \
  --network "$NETWORK" \
  -e POSTGRES_DB="$KC_DB_NAME" \
  -e POSTGRES_USER="$KC_DB_USER" \
  -e POSTGRES_PASSWORD="$KC_DB_PASSWORD" \
  -v "$KC_DB_MOUNT" \
  "$KC_POSTGRES_IMAGE"

echo "[keycloak] waiting for Postgres..."
for _ in {1..30}; do
  if docker exec keycloak-db pg_isready -U "$KC_DB_USER" -d "$KC_DB_NAME" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[keycloak] starting Keycloak..."
docker run -d \
  --name keycloak \
  --restart "$RESTART_POLICY" \
  --network "$NETWORK" \
  -p "$KC_HTTP_PORT:8080" \
  -e KC_DB=postgres \
  -e KC_DB_URL="jdbc:postgresql://keycloak-db:5432/$KC_DB_NAME" \
  -e KC_DB_USERNAME="$KC_DB_USER" \
  -e KC_DB_PASSWORD="$KC_DB_PASSWORD" \
  -e KC_HOSTNAME="$KC_HOSTNAME" \
  -e KC_HOSTNAME_STRICT="$KC_HOSTNAME_STRICT" \
  -e KC_HTTP_ENABLED="$KC_HTTP_ENABLED" \
  -e KC_PROXY_HEADERS="$KC_PROXY_HEADERS" \
  -e KC_BOOTSTRAP_ADMIN_USERNAME="$KC_BOOTSTRAP_ADMIN" \
  -e KC_BOOTSTRAP_ADMIN_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" \
  "$KEYCLOAK_IMAGE" \
  start-dev

echo "[keycloak] waiting for Keycloak readiness..."
KC_READY=false
for _ in {1..60}; do
  if curl -sf "http://localhost:${KC_HTTP_PORT}/realms/master/.well-known/openid-configuration" >/dev/null 2>&1; then
    KC_READY=true
    break
  fi
  sleep 3
done

if [ "$KC_READY" != "true" ]; then
  echo "[keycloak] failed to start, see logs:"
  docker logs keycloak --tail 80
  exit 1
fi

echo "[keycloak] running bootstrap (realm/clients/roles)..."
KC_BASE_URL="http://localhost:${KC_HTTP_PORT}" \
KC_BOOTSTRAP_ADMIN="$KC_BOOTSTRAP_ADMIN" \
KC_BOOTSTRAP_ADMIN_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" \
KC_REALM="$REALM" \
  bash "$ROOT/keycloak/bootstrap-realm.sh"

echo "[keycloak] done."
echo "  admin console:  http://${KC_HOSTNAME}:${KC_HTTP_PORT}/  (user=$KC_BOOTSTRAP_ADMIN)"
echo "  realm issuer:   http://${KC_HOSTNAME}:${KC_HTTP_PORT}/realms/${REALM}"
