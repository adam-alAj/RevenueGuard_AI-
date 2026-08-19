#!/usr/bin/env bash
# RevenueGuard AI — Deployment Script
#
# Usage:
#   ./scripts/deploy.sh                  # Deploy with defaults
#   ./scripts/deploy.sh --build-only     # Build images without starting
#   ./scripts/deploy.sh --migrate-only   # Run migrations only
#
# Prerequisites:
#   - Docker and Docker Compose v2 installed
#   - Environment variables set (GEMINI_API_KEY, JWT_SECRET, POSTGRES_PASSWORD)
#   - Or a .env file in the project root with those values

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="docker-compose.prod.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[deploy]${NC} $1"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $1"; }
error() { echo -e "${RED}[deploy]${NC} $1" >&2; exit 1; }

# ─── Parse arguments ─────────────────────────────────────────────────────────

BUILD_ONLY=false
MIGRATE_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only) BUILD_ONLY=true; shift ;;
        --migrate-only) MIGRATE_ONLY=true; shift ;;
        *) error "Unknown argument: $1" ;;
    esac
done

# ─── Validate environment ────────────────────────────────────────────────────

log "Validating environment..."

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    error "GEMINI_API_KEY is not set. Export it or add it to .env"
fi

if [[ -z "${JWT_SECRET:-}" ]]; then
    error "JWT_SECRET is not set. Export it or add it to .env"
fi

if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
    warn "POSTGRES_PASSWORD not set, using default (change for production!)"
    export POSTGRES_PASSWORD="changeme-in-production"
fi

log "Environment validated."

# ─── Build images ────────────────────────────────────────────────────────────

log "Building Docker images..."
cd "$PROJECT_DIR"
docker compose -f "$COMPOSE_FILE" build --no-cache

if [[ "$BUILD_ONLY" == "true" ]]; then
    log "Build complete. Images ready."
    exit 0
fi

# ─── Run database migrations ────────────────────────────────────────────────

log "Starting database..."
docker compose -f "$COMPOSE_FILE" up -d db
sleep 5  # Wait for DB to be ready

log "Running database migrations..."
docker compose -f "$COMPOSE_FILE" run --rm backend python -m alembic upgrade head

if [[ "$MIGRATE_ONLY" == "true" ]]; then
    log "Migrations complete."
    exit 0
fi

# ─── Start all services ─────────────────────────────────────────────────────

log "Starting all services..."
docker compose -f "$COMPOSE_FILE" up -d

# ─── Health checks ──────────────────────────────────────────────────────────

log "Waiting for services to become healthy..."
MAX_WAIT=60
ELAPSED=0

while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    BACKEND_HEALTH=$(docker compose -f "$COMPOSE_FILE" ps --format json backend 2>/dev/null | grep -o '"Health":"[^"]*"' | head -1 || echo '"Health":"unknown"')
    if echo "$BACKEND_HEALTH" | grep -q "healthy"; then
        log "Backend is healthy."
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo -n "."
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    error "Backend did not become healthy within ${MAX_WAIT}s. Check logs with: docker compose -f $COMPOSE_FILE logs backend"
fi

# ─── Verify health endpoint ────────────────────────────────────────────────

log "Verifying health endpoint..."
BACKEND_PORT="${BACKEND_PORT:-8000}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${BACKEND_PORT}/health" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
    log "Health check passed (HTTP 200)."
else
    warn "Health check returned HTTP $HTTP_CODE — this may be expected if the port is mapped differently."
fi

# ─── Summary ────────────────────────────────────────────────────────────────

echo ""
log "══════════════════════════════════════════════════════════════"
log "  Deployment complete!"
log "  Backend:  http://localhost:${BACKEND_PORT}"
log "  Frontend: http://localhost:${FRONTEND_PORT:-80}"
log "  Postgres: localhost:5432 (internal only)"
log ""
log "  View logs:    docker compose -f $COMPOSE_FILE logs -f"
log "  Stop:         docker compose -f $COMPOSE_FILE down"
log "  Rollback:     ./scripts/rollback.sh"
log "══════════════════════════════════════════════════════════════"
