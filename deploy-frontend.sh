#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)

FRONTEND_IMAGE=${FRONTEND_IMAGE:-mr-frontend:arm64}
NETWORK=${NETWORK:-mr-net}

VITE_TUSD_ENDPOINT=${VITE_TUSD_ENDPOINT:-/files}
VITE_TUSD_PATH_PREFIX=${VITE_TUSD_PATH_PREFIX:-\\\\192.168.1.224\\upload\\}

docker build -t "$FRONTEND_IMAGE" -f "$ROOT/frontend/Dockerfile" "$ROOT/frontend" --build-arg VITE_TUSD_ENDPOINT="$VITE_TUSD_ENDPOINT" --build-arg VITE_TUSD_PATH_PREFIX="$VITE_TUSD_PATH_PREFIX"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK"

docker rm -f frontend >/dev/null 2>&1 || true

docker run -d --name frontend --network "$NETWORK" -p 80:80 "$FRONTEND_IMAGE"
