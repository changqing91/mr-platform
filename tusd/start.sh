#!/bin/sh
set -eu

echo "[tusd-hook] Starting hook server on port ${TUSD_HOOK_PORT}"
exec node /app/tusd-hook-rename.js
