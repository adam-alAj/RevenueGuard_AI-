# RevenueGuard AI — Deployment Runbook

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker Host                        │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │ Frontend  │───▶│ Backend  │───▶│ Postgres     │  │
│  │ (nginx)   │    │ (uvicorn)│    │ (managed)    │  │
│  │ :80       │    │ :8000    │    │ :5432        │  │
│  └──────────┘    └──────────┘    └──────────────┘  │
│                                                      │
│  No Kubernetes. No service mesh. Simple.             │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker and Docker Compose v2 installed
- A managed Postgres instance (or local Docker Postgres for dev/staging)
- Google Gemini API key
- Sufficient memory: 512MB for backend, 128MB for frontend, 1GB for Postgres

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `JWT_SECRET` | Yes | Secret for signing JWT tokens (min 32 chars) |
| `POSTGRES_PASSWORD` | Yes | Postgres password |
| `APP_ENV` | No | `production` (default: `development`) |
| `DEBUG` | No | `false` in production (default: `false`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (e.g., `https://app.example.com`) |
| `BACKEND_PORT` | No | Backend port (default: `8000`) |
| `FRONTEND_PORT` | No | Frontend port (default: `80`) |
| `GEMINI_MODEL` | No | Gemini model (default: `gemini-2.0-flash`) |

## First-Time Deployment

### 1. Set up secrets

```bash
# Create a .env file (NEVER commit this)
cat > .env << 'EOF'
GEMINI_API_KEY=your-gemini-api-key
JWT_SECRET=your-random-secret-min-32-chars
POSTGRES_PASSWORD=your-strong-postgres-password
CORS_ORIGINS=https://your-domain.com
EOF
```

### 2. Deploy

```bash
./scripts/deploy.sh
```

This will:
1. Build backend and frontend Docker images
2. Start Postgres and run migrations
3. Start all services
4. Verify health checks pass

### 3. Verify

```bash
# Check all services are running
docker compose -f docker-compose.prod.yml ps

# Check backend health
curl http://localhost:8000/health

# Check frontend
curl -s http://localhost/ | head -5
```

## Deploying a New Version

```bash
# Pull latest code
git pull origin main

# Deploy (builds new images, runs migrations, restarts services)
./scripts/deploy.sh
```

### What happens during deployment:
1. New Docker images are built (with `--no-cache` for reproducibility)
2. Database migrations run automatically via `alembic upgrade head`
3. Backend is restarted with the new image
4. Health checks verify the new version is working
5. Frontend is restarted with the new static build

### Zero-downtime considerations:
- The backend uses 4 uvicorn workers — during restart, there's a brief window (~5s) where requests may fail
- For true zero-downtime, use a load balancer with health-check-based routing
- Database migrations must be backward-compatible (additive changes only)

## Rolling Back

### Quick rollback (restart previous image):

```bash
./scripts/rollback.sh
```

### Rollback with migration revert:

```bash
# Roll back to a specific migration
./scripts/rollback.sh --migration <alembic-revision>

# Example: roll back the last migration
./scripts/rollback.sh --migration -1
```

### Manual rollback:

```bash
# Stop current backend
docker compose -f docker-compose.prod.yml stop backend

# Start with the previous image tag (if you tagged it)
docker compose -f docker-compose.prod.yml up -d backend

# Verify health
curl http://localhost:8000/health
```

## Rotating the Gemini API Key

This can be done without downtime:

1. **Generate a new key** in Google AI Studio
2. **Update the environment variable** (restart required for the key to take effect):
   ```bash
   # Update .env with new key
   # Then restart the backend
   docker compose -f docker-compose.prod.yml restart backend
   ```
3. **Verify** the new key works:
   ```bash
   # Check agent smoke test
   curl -X POST http://localhost:8000/api/v1/agents/smoke-test \
     -H "Authorization: Bearer <your-token>"
   ```

## Restoring from Postgres Backup

### Create a backup:

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U revenueguard -d revenueguard > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore from backup:

```bash
# Stop the backend first
docker compose -f docker-compose.prod.yml stop backend

# Restore the database
cat backup_20250101_120000.sql | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U revenueguard -d revenueguard

# Restart the backend
docker compose -f docker-compose.prod.yml start backend
```

### Automated daily backups (add to crontab):

```bash
# Add to crontab: backup every day at 2 AM
0 2 * * * cd /path/to/project && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U revenueguard -d revenueguard | gzip > /backups/revenueguard_$(date +\%Y\%m\%d).sql.gz
```

## Monitoring

### Health endpoints:

```bash
# Backend health
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# Frontend health
curl http://localhost/health
# Expected: {"status": "ok"}
```

### Logs:

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Backend only
docker compose -f docker-compose.prod.yml logs -f backend

# Database only
docker compose -f docker-compose.prod.yml logs -f db
```

### Observability:

```bash
# List execution traces
curl http://localhost:8000/api/v1/observability/traces \
  -H "Authorization: Bearer <token>"

# Get aggregated metrics
curl http://localhost:8000/api/v1/observability/metrics \
  -H "Authorization: Bearer <token>"
```

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs backend

# Common causes:
# - Missing GEMINI_API_KEY or JWT_SECRET → app refuses to start
# - Database not ready → wait for health check
# - Port already in use → change BACKEND_PORT
```

### Database connection refused

```bash
# Check if Postgres is running
docker compose -f docker-compose.prod.yml ps db

# Check Postgres logs
docker compose -f docker-compose.prod.yml logs db

# Verify DATABASE_URL is correct
docker compose -f docker-compose.prod.yml exec db \
  pg_isready -U revenueguard -d revenueguard
```

### Migration fails

```bash
# Check current migration state
docker compose -f docker-compose.prod.yml run --rm backend \
  python -m alembic current

# Check migration history
docker compose -f docker-compose.prod.yml run --rm backend \
  python -m alembic history

# Roll back to last working state
docker compose -f docker-compose.prod.yml run --rm backend \
  python -m alembic downgrade -1
```

## Security Checklist

Before going to production, verify:

- [ ] `APP_ENV=production` is set
- [ ] `DEBUG=false` is set
- [ ] `JWT_SECRET` is a strong random string (min 32 chars)
- [ ] `GEMINI_API_KEY` is set and not committed to git
- [ ] `POSTGRES_PASSWORD` is strong and not committed to git
- [ ] `CORS_ORIGINS` is set to your actual domain(s)
- [ ] Postgres is NOT exposed on public ports (only Docker network)
- [ ] No `.env` files are committed to git
- [ ] Security scan passes: `pytest tests/test_tenant_isolation_adversarial.py`
- [ ] Rate limiting is active on auth endpoints
- [ ] SSL/TLS is terminated at the load balancer/reverse proxy (not shown here)
