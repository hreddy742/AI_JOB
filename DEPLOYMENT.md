# Deployment Guide (VPS)

This deploys the existing production stack in `docker-compose.prod.yml` so others can use the app.

## 1. VPS Requirements

- Ubuntu 22.04+ (or Debian)
- Recommended: 4 vCPU, 8 GB RAM, 50+ GB disk
- Ports open: `80` (and `443` later when adding TLS)

## 2. Server Bootstrap

Run on the VPS:

```bash
git clone https://github.com/hreddy742/AI_JOB.git
cd AI_JOB/apex-apply
bash scripts/install_vps_prereqs.sh
```

Re-login once if docker group permissions were updated.

## 3. Configure Environment

```bash
cp .env.production.example .env
```

Edit `.env` and set strong values at minimum:

- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `TYPESENSE_API_KEY`
- `FRONTEND_URL` (public URL)

## 4. Deploy

```bash
bash scripts/deploy_vps.sh
```

This performs:

- `docker compose -f docker-compose.prod.yml up -d --build`
- `alembic upgrade head`
- API and Web health checks

## 5. Verify Public Access

- API: `http://<SERVER_IP_OR_DOMAIN>/api/health`
- Web login: `http://<SERVER_IP_OR_DOMAIN>/login`
- Web register: `http://<SERVER_IP_OR_DOMAIN>/register`

## 6. Update / Redeploy

```bash
git pull
bash scripts/deploy_vps.sh
```

## 7. Optional: HTTPS

For public usage, add TLS (recommended) with Cloudflare tunnel, Caddy, or Nginx + Let's Encrypt.
