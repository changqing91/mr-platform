#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)

SERVER_IMAGE=${SERVER_IMAGE:-mr-server:arm64}
MYSQL_IMAGE=${MYSQL_IMAGE:-mysql:8.0}
NETWORK=${NETWORK:-mr-net}

APP_KEYS=${APP_KEYS:-key1,key2}
API_TOKEN_SALT=${API_TOKEN_SALT:-salt}
ADMIN_JWT_SECRET=${ADMIN_JWT_SECRET:-secret}
TRANSFER_TOKEN_SALT=${TRANSFER_TOKEN_SALT:-salt}
JWT_SECRET=${JWT_SECRET:-secret}
ENCRYPTION_KEY=${ENCRYPTION_KEY:-secret}

MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_DATABASE=${MYSQL_DATABASE:-strapi}
MYSQL_USER=${MYSQL_USER:-strapi}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-strapi}
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:-root}
MYSQL_DATA_HOST_DIR=${MYSQL_DATA_HOST_DIR:-}
MYSQL_DATA_VOLUME=${MYSQL_DATA_VOLUME:-mr-mysql}

STRAPI_UPLOADS_HOST_DIR=${STRAPI_UPLOADS_HOST_DIR:-/srv/mr/server/uploads}

if ! mkdir -p "$STRAPI_UPLOADS_HOST_DIR" >/dev/null 2>&1; then
  STRAPI_UPLOADS_HOST_DIR="$ROOT/.data/strapi-uploads"
  mkdir -p "$STRAPI_UPLOADS_HOST_DIR"
fi

if [ -n "${MYSQL_DATA_HOST_DIR}" ]; then
  if ! mkdir -p "$MYSQL_DATA_HOST_DIR" >/dev/null 2>&1; then
    MYSQL_DATA_HOST_DIR="$ROOT/.data/mysql"
    mkdir -p "$MYSQL_DATA_HOST_DIR"
  fi
  MYSQL_DATA_MOUNT="$MYSQL_DATA_HOST_DIR:/var/lib/mysql"
else
  docker volume inspect "$MYSQL_DATA_VOLUME" >/dev/null 2>&1 || docker volume create "$MYSQL_DATA_VOLUME" >/dev/null
  MYSQL_DATA_MOUNT="$MYSQL_DATA_VOLUME:/var/lib/mysql"
fi

docker build -t "$SERVER_IMAGE" -f "$ROOT/server/Dockerfile" "$ROOT/server"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"

docker rm -f mysql >/dev/null 2>&1 || true
docker rm -f server >/dev/null 2>&1 || true

docker run -d --name mysql --network "$NETWORK" -p "$MYSQL_PORT:3306" -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASSWORD" -e MYSQL_DATABASE="$MYSQL_DATABASE" -e MYSQL_USER="$MYSQL_USER" -e MYSQL_PASSWORD="$MYSQL_PASSWORD" -v "$MYSQL_DATA_MOUNT" "$MYSQL_IMAGE"

MYSQL_READY=false
for _ in {1..30}; do
  if docker exec mysql mysqladmin ping -h 127.0.0.1 -p"$MYSQL_ROOT_PASSWORD" --silent >/dev/null 2>&1; then
    MYSQL_READY=true
    break
  fi
  sleep 2
done

if [ "$MYSQL_READY" != "true" ]; then
  docker logs mysql --tail 50
  exit 1
fi

docker run -d --name server --network "$NETWORK" -p 1337:1337 -e HOST=0.0.0.0 -e PORT=1337 -e DATABASE_CLIENT=mysql -e DATABASE_HOST=mysql -e DATABASE_PORT=3306 -e DATABASE_NAME="$MYSQL_DATABASE" -e DATABASE_USERNAME="$MYSQL_USER" -e DATABASE_PASSWORD="$MYSQL_PASSWORD" -e APP_KEYS="$APP_KEYS" -e API_TOKEN_SALT="$API_TOKEN_SALT" -e ADMIN_JWT_SECRET="$ADMIN_JWT_SECRET" -e TRANSFER_TOKEN_SALT="$TRANSFER_TOKEN_SALT" -e JWT_SECRET="$JWT_SECRET" -e ENCRYPTION_KEY="$ENCRYPTION_KEY" -v "$STRAPI_UPLOADS_HOST_DIR:/app/public/uploads" "$SERVER_IMAGE"
