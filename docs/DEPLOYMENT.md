# Deployment (AWS Mumbai, Docker Compose)

> The Docker files, nginx config and backup script were written carefully but **not executed** when this project was generated.
> Expect to fix small things on the first run; the application itself (tests, build) was verified.

## 1. One-time server setup
1. Create an AWS account, region **ap-south-1 (Mumbai)**. Launch an Ubuntu 24.04 EC2 instance (start with 2 vCPU / 4 GB, e.g. t3.medium) with a 30 GB disk. Security group: open 22 (your IP only), 80, 443.
2. Allocate an Elastic IP and point an A record (`app.yourdomain.in`) to it at your domain registrar.
3. On the server (SSH):
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git nginx certbot python3-certbot-nginx
sudo usermod -aG docker $USER   # log out and in again
git clone <your github repo> /opt/zeal && cd /opt/zeal
cp .env.production.example .env.production && nano .env.production   # real secret key, strong DB password, your domain
```
## 2. Start
```bash
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production exec backend python manage.py seed_initial       # units, settings, location (no demo users)
docker compose --env-file .env.production exec backend python manage.py createsuperuser    # your owner login
```
The app now answers on `127.0.0.1:8080`.
## 3. HTTPS
Create `/etc/nginx/sites-available/zeal`:
```nginx
server { server_name app.yourdomain.in; client_max_body_size 10m;
  location / { proxy_pass http://127.0.0.1:8080; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; } }
```
```bash
sudo ln -s /etc/nginx/sites-available/zeal /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d app.yourdomain.in      # free certificate, auto-renews
```
Open `https://app.yourdomain.in`, log in, then Settings (GSTIN, scheme, rates). On phones: browser menu → **Add to Home Screen** (Android Chrome: Install app; iPhone Safari: Share → Add to Home Screen).
Run `docker compose --env-file .env.production exec backend python manage.py check --deploy`.

## 4. Backups and restore test
```bash
./deploy/backup.sh                        # nightly via cron: 30 2 * * * /opt/zeal/deploy/backup.sh
```
Also copy dumps off the server (S3 bucket with lifecycle rule). **Test a restore** into a scratch database at least once:
```bash
docker compose --env-file .env.production exec -T db createdb -U zeal zeal_restore_test
docker compose --env-file .env.production exec -T db pg_restore -U zeal -d zeal_restore_test < backups/zeal-YYYYMMDD-HHMM.dump
```
## 5. Updates and rollback
```bash
cd /opt/zeal && git pull && docker compose --env-file .env.production up -d --build   # migrations run automatically on start
git log --oneline -5; git checkout <previous commit>; docker compose --env-file .env.production up -d --build   # rollback code
```
Take a backup **before** every update; a rollback of code does not undo a database migration (restore the backup for that).

## 6. Monitoring and logs
`docker compose logs -f backend worker`. Add free-tier **Sentry** (`pip install sentry-sdk`, init in `settings.py`) for error alerts and UptimeRobot on `/api/v1/health/` for downtime alerts.

## Cost estimate (small business, monthly, approximate; check current AWS/provider prices)
| Item | Approx. | Recurring? |
|---|---|---|
| EC2 t3.medium Mumbai + 30 GB disk + Elastic IP | ₹3,000–4,500 | monthly |
| Backups (S3 / snapshots) | ₹100–500 | monthly |
| Domain (.in) | ₹600–1,200 | yearly |
| TLS certificate (Let's Encrypt) | ₹0 | |
| Sentry / UptimeRobot free tiers | ₹0 | |
| SMS (needs DLT registration), WhatsApp Business API, Razorpay fees | usage based | per message / per transaction |
A cheaper start is a smaller instance (t3.small) and add RDS later only if needed.
