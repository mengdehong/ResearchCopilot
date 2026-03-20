#!/usr/bin/env bash
# deployment/healthcheck.sh — 全栈健康检查脚本
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check() {
    local name="$1"
    local url="$2"
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} ${name}"
    else
        echo -e "${RED}✗${NC} ${name} — ${url}"
        FAILED=1
    fi
}

FAILED=0

echo "=== Research Copilot Health Check ==="
echo ""

check "Backend API"    "http://localhost:8000/api/health"
check "Frontend"       "http://localhost:80"
check "Nginx Proxy"    "http://localhost:80/api/health"
check "Prometheus"     "http://localhost:9090/-/healthy"
check "Grafana"        "http://localhost:3000/api/health"

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}All services healthy.${NC}"
else
    echo -e "${RED}Some services are unhealthy!${NC}"
    exit 1
fi
