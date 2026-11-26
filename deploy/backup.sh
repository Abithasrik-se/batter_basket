#!/usr/bin/env bash
# Nightly PostgreSQL backup. Cron example (as the deploy user):  30 2 * * * /opt/zeal/deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M)
docker compose --env-file .env.production exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "backups/zeal-$STAMP.dump"
# keep 14 days locally; ALSO copy to off-site storage (e.g. aws s3 cp backups/zeal-$STAMP.dump s3://your-bucket/)
find backups -name 'zeal-*.dump' -mtime +14 -delete
echo "Backup written: backups/zeal-$STAMP.dump"
