#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)

TUSD_IMAGE=${TUSD_IMAGE:-tusproject/tusd:latest}
TUSD_HOOK_IMAGE=${TUSD_HOOK_IMAGE:-mr-tusd-hook:arm64}
NETWORK=${NETWORK:-mr-net}

TUSD_PORT=${TUSD_PORT:-9000}
TUSD_HOOK_PORT=${TUSD_HOOK_PORT:-3001}
TUSD_UPLOAD_DIR=${TUSD_UPLOAD_DIR:-/data/uploads}
TUSD_BASE_PATH=${TUSD_BASE_PATH:-/files}

UPLOADS_HOST_DIR=${UPLOADS_HOST_DIR:-/mnt/upload}

docker build -t "$TUSD_HOOK_IMAGE" -f "$ROOT/tusd/Dockerfile" "$ROOT/tusd"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"

if ! mkdir -p "$UPLOADS_HOST_DIR" >/dev/null 2>&1; then
  UPLOADS_HOST_DIR="$ROOT/.data/uploads"
  mkdir -p "$UPLOADS_HOST_DIR"
fi

docker rm -f tusd tusd-hook >/dev/null 2>&1 || true

docker run -d --name tusd-hook --network "$NETWORK" -p "$TUSD_HOOK_PORT:$TUSD_HOOK_PORT" -e TUSD_HOOK_PORT="$TUSD_HOOK_PORT" -e TUSD_UPLOAD_DIR="$TUSD_UPLOAD_DIR" -v "$UPLOADS_HOST_DIR:$TUSD_UPLOAD_DIR" "$TUSD_HOOK_IMAGE"

docker run -d --name tusd --network "$NETWORK" -p "$TUSD_PORT:$TUSD_PORT" -e TUSD_PORT="$TUSD_PORT" -e TUSD_UPLOAD_DIR="$TUSD_UPLOAD_DIR" -e TUSD_BASE_PATH="$TUSD_BASE_PATH" -v "$UPLOADS_HOST_DIR:$TUSD_UPLOAD_DIR" "$TUSD_IMAGE" \
  -port "$TUSD_PORT" \
  -upload-dir "$TUSD_UPLOAD_DIR" \
  -base-path "$TUSD_BASE_PATH" \
  -hooks-http "http://tusd-hook:${TUSD_HOOK_PORT}/hooks" \
  -hooks-enabled-events "post-finish"
