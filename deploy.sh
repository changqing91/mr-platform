#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)

FRONTEND_IMAGE=${FRONTEND_IMAGE:-mr-frontend:arm64}
SERVER_IMAGE=${SERVER_IMAGE:-mr-server:arm64}
TUSD_IMAGE=${TUSD_IMAGE:-tusproject/tusd:latest}
TUSD_HOOK_IMAGE=${TUSD_HOOK_IMAGE:-mr-tusd-hook:arm64}
MYSQL_IMAGE=${MYSQL_IMAGE:-mysql:8.0}
NETWORK=${NETWORK:-mr-net}

VITE_TUSD_ENDPOINT=${VITE_TUSD_ENDPOINT:-/files}
VITE_TUSD_PATH_PREFIX=${VITE_TUSD_PATH_PREFIX:-\\\\192.168.1.224\\upload\\}

TUSD_PORT=${TUSD_PORT:-9000}
TUSD_HOOK_PORT=${TUSD_HOOK_PORT:-3001}
TUSD_UPLOAD_DIR=${TUSD_UPLOAD_DIR:-/data/uploads}
TUSD_BASE_PATH=${TUSD_BASE_PATH:-/files}
UPLOADS_HOST_DIR=${UPLOADS_HOST_DIR:-/mnt/upload}
STRAPI_UPLOADS_HOST_DIR=${STRAPI_UPLOADS_HOST_DIR:-/srv/mr/server/uploads}

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

docker build -t "$FRONTEND_IMAGE" -f "$ROOT/frontend/Dockerfile" "$ROOT/frontend" --build-arg VITE_TUSD_ENDPOINT="$VITE_TUSD_ENDPOINT" --build-arg VITE_TUSD_PATH_PREFIX="$VITE_TUSD_PATH_PREFIX"
docker build -t "$SERVER_IMAGE" -f "$ROOT/server/Dockerfile" "$ROOT/server"
docker build -t "$TUSD_HOOK_IMAGE" -f "$ROOT/tusd/Dockerfile" "$ROOT/tusd"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"

if ! mkdir -p "$UPLOADS_HOST_DIR" >/dev/null 2>&1 || ! mkdir -p "$STRAPI_UPLOADS_HOST_DIR" >/dev/null 2>&1; then
  UPLOADS_HOST_DIR="$ROOT/.data/uploads"
  STRAPI_UPLOADS_HOST_DIR="$ROOT/.data/strapi-uploads"
  mkdir -p "$UPLOADS_HOST_DIR" "$STRAPI_UPLOADS_HOST_DIR"
fi
chmod -R 0777 "$UPLOADS_HOST_DIR" >/dev/null 2>&1 || true

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

docker rm -f tusd tusd-hook >/dev/null 2>&1 || true
docker rm -f mysql >/dev/null 2>&1 || true
docker rm -f server >/dev/null 2>&1 || true
docker rm -f frontend >/dev/null 2>&1 || true

docker run -d --name tusd-hook --network "$NETWORK" -p "$TUSD_HOOK_PORT:$TUSD_HOOK_PORT" -e TUSD_HOOK_PORT="$TUSD_HOOK_PORT" -e TUSD_UPLOAD_DIR="$TUSD_UPLOAD_DIR" -v "$UPLOADS_HOST_DIR:$TUSD_UPLOAD_DIR" "$TUSD_HOOK_IMAGE"
docker run -d --name tusd --network "$NETWORK" -p "$TUSD_PORT:$TUSD_PORT" -e TUSD_PORT="$TUSD_PORT" -e TUSD_UPLOAD_DIR="$TUSD_UPLOAD_DIR" -e TUSD_BASE_PATH="$TUSD_BASE_PATH" -v "$UPLOADS_HOST_DIR:$TUSD_UPLOAD_DIR" "$TUSD_IMAGE" \
  -port "$TUSD_PORT" \
  -upload-dir "$TUSD_UPLOAD_DIR" \
  -base-path "$TUSD_BASE_PATH" \
  -hooks-http "http://tusd-hook:${TUSD_HOOK_PORT}/hooks" \
  -hooks-enabled-events "post-finish"

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

docker run -d --name frontend --network "$NETWORK" -p 80:80 "$FRONTEND_IMAGE"

echo "deploy ok"
