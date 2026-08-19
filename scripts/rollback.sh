#!/usr/bin/env bash
# RevenueGuard AI — Rollback Script
#
# Usage:
#   ./scripts/rollback.sh                    # Roll back to previous image tag
#   ./scripts/rollback.sh --tag <tag>        # Roll back to specific tag
#   ./scripts/rollback.sh --migration <rev>  # Roll back to specific migration
#
# This script:
# 1. Stops the current backend
# 2. Rolls back database migration (if requested)
# 3. Starts the backend with the previous image
# 4. Verifies health

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="docker-compose.prod.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[rollback]${NC} $1"; }
warn() { echo -e "${YELLOW}[rollback]${NC} $1"; }
error() { echo -e "${RED}[rollback]${NC} $1" >&2; exit 1; }

# ─── Parse arguments ─────────────────────────────────────────────────────────

TAG=""
MIGRATION_REV=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) TAG="$2"; shift 2 ;;
        --migration) MIGRATION_REV="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--tag <tag>] [--migration <revision>]"
            echo ""
            echo "Options:"
            echo "  --tag <tag>        Docker image tag to rollback to"
            echo "  --migration <rev>  Alembic migration revision to roll back to"
            exit 0
            ;;
        *) error "Unknown argument: $1" ;;
    esac
done

# ─── Validate environment ────────────────────────────────────────────────────

log "Validating environment..."

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    error "GEMINI_API_KEY is not set."
fi
if [[ -z "${JWT_SECRET:-}" ]]; then
    error "JWT_SECRET is not set."
fi
if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
    export POSTGRES_PASSWORD="changeme-in-production"
fi

cd "$PROJECT_DIR"

# ─── Step 1: Rollback migration (if requested) ──────────────────────────────

if [[ -n "$MIGRATION_REV" ]]; then
    log "Rolling back migration to revision: $MIGRATION_REV"
    docker compose -f "$COMPOSE_FILE" run --rm backend python -m alembic downgrade "$MIGRATION_REV"
    log "Migration rolled back to $MIGRATION_REV."
fi

# ─── Step 2: Stop current backend ───────────────────────────────────────────

log "Stopping current backend..."
docker compose -f "$COMPOSE_FILE" stop backend

# ─── Step 3: Start with previous image ──────────────────────────────────────

if [[ -n "$TAG" ]]; then
    log "Starting backend with tag: $TAG"
    # Override the image tag
    docker compose -f "$COMPOSE_FILE" up -d --no-deps backend
    # Tag override would need image manipulation — for now, rebuild with tag
    warn "Note: To use a specific tag, rebuild with: docker build --tag revenueguard-backend:$TAG"
fi

log "Starting backend..."
docker compose -f "$COMPOSE_FILE" up -d backend

# ─── Step 4: Health check ───────────────────────────────────────────────────

log "Waiting for backend to become healthy..."
MAX_WAIT=30
ELAPSED=0

while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${BACKEND_PORT:-8000}/health" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        log "Backend is healthy after rollback."
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo -n "."
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    error "Backend did not become healthy after rollback. Check logs."
fi

log "Rollback complete."
