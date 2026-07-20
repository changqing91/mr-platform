#!/usr/bin/env bash
set -euo pipefail

NETWORK=${NETWORK:-mr-net}
CONTAINERS="tusd tusd-hook mysql server frontend keycloak keycloak-db"

echo "Stopping and removing containers..."
for c in $CONTAINERS; do
  if docker ps -a --format '{{.Names}}' | grep -qx "$c"; then
    docker rm -f "$c" >/dev/null 2>&1 && echo "  [removed] $c" || echo "  [failed]  $c"
  else
    echo "  [skip]    $c (not found)"
  fi
done

echo ""
echo "Remaining related containers:"
docker ps -a --filter "name=tusd" --filter "name=mysql" --filter "name=server" \
  --filter "name=frontend" --filter "name=keycloak" \
  --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true

echo ""
echo "Data volumes and host directories are preserved."
echo "To redeploy: ./deploy.sh && ./deploy-keycloak.sh"
