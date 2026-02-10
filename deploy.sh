#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)

FRONTEND_IMAGE=${FRONTEND_IMAGE:-mr-frontend:arm64}
SERVER_IMAGE=${SERVER_IMAGE:-mr-server:arm64}
TUSD_IMAGE=${TUSD_IMAGE:-tusproject/tusd:latest}
TUSD_HOOK_IMAGE=${TUSD_HOOK_IMAGE:-mr-tusd-hook:arm64}
NETWORK=${NETWORK:-mr-net}

VITE_TUSD_ENDPOINT=${VITE_TUSD_ENDPOINT:-/files}
VITE_TUSD_PATH_PREFIX=${VITE_TUSD_PATH_PREFIX:-/uploads}

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

docker rm -f tusd tusd-hook >/dev/null 2>&1 || true
docker rm -f server >/dev/null 2>&1 || true
docker rm -f frontend >/dev/null 2>&1 || true

docker run -d --name tusd-hook --network "$NETWORK" -p "$TUSD_HOOK_PORT:$TUSD_HOOK_PORT" -e TUSD_HOOK_PORT="$TUSD_HOOK_PORT" -e TUSD_UPLOAD_DIR="$TUSD_UPLOAD_DIR" -v "$UPLOADS_HOST_DIR:$TUSD_UPLOAD_DIR" "$TUSD_HOOK_IMAGE"
docker run -d --name tusd --network "$NETWORK" -p "$TUSD_PORT:$TUSD_PORT" -e TUSD_PORT="$TUSD_PORT" -e TUSD_UPLOAD_DIR="$TUSD_UPLOAD_DIR" -e TUSD_BASE_PATH="$TUSD_BASE_PATH" -v "$UPLOADS_HOST_DIR:$TUSD_UPLOAD_DIR" "$TUSD_IMAGE" \
  -port "$TUSD_PORT" \
  -upload-dir "$TUSD_UPLOAD_DIR" \
  -base-path "$TUSD_BASE_PATH" \
  -hooks-http "http://tusd-hook:${TUSD_HOOK_PORT}/hooks" \
  -hooks-enabled-events "post-finish"

docker run -d --name server --network "$NETWORK" -p 1337:1337 -e HOST=0.0.0.0 -e PORT=1337 -e APP_KEYS="$APP_KEYS" -e API_TOKEN_SALT="$API_TOKEN_SALT" -e ADMIN_JWT_SECRET="$ADMIN_JWT_SECRET" -e TRANSFER_TOKEN_SALT="$TRANSFER_TOKEN_SALT" -e JWT_SECRET="$JWT_SECRET" -e ENCRYPTION_KEY="$ENCRYPTION_KEY" -v "$STRAPI_UPLOADS_HOST_DIR:/app/public/uploads" "$SERVER_IMAGE"

docker run -d --name frontend --network "$NETWORK" -p 80:80 "$FRONTEND_IMAGE"

echo "deploy ok"
