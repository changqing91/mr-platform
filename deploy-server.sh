#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)

SERVER_IMAGE=${SERVER_IMAGE:-mr-server:arm64}
NETWORK=${NETWORK:-mr-net}

APP_KEYS=${APP_KEYS:-key1,key2}
API_TOKEN_SALT=${API_TOKEN_SALT:-salt}
ADMIN_JWT_SECRET=${ADMIN_JWT_SECRET:-secret}
TRANSFER_TOKEN_SALT=${TRANSFER_TOKEN_SALT:-salt}
JWT_SECRET=${JWT_SECRET:-secret}
ENCRYPTION_KEY=${ENCRYPTION_KEY:-secret}

STRAPI_UPLOADS_HOST_DIR=${STRAPI_UPLOADS_HOST_DIR:-/srv/mr/server/uploads}

if ! mkdir -p "$STRAPI_UPLOADS_HOST_DIR" >/dev/null 2>&1; then
  STRAPI_UPLOADS_HOST_DIR="$ROOT/.data/strapi-uploads"
  mkdir -p "$STRAPI_UPLOADS_HOST_DIR"
fi

docker build -t "$SERVER_IMAGE" -f "$ROOT/server/Dockerfile" "$ROOT/server"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"

docker rm -f server >/dev/null 2>&1 || true

docker run -d --name server --network "$NETWORK" -p 1337:1337 -e HOST=0.0.0.0 -e PORT=1337 -e APP_KEYS="$APP_KEYS" -e API_TOKEN_SALT="$API_TOKEN_SALT" -e ADMIN_JWT_SECRET="$ADMIN_JWT_SECRET" -e TRANSFER_TOKEN_SALT="$TRANSFER_TOKEN_SALT" -e JWT_SECRET="$JWT_SECRET" -e ENCRYPTION_KEY="$ENCRYPTION_KEY" -v "$STRAPI_UPLOADS_HOST_DIR:/app/public/uploads" "$SERVER_IMAGE"
