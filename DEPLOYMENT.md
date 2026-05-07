# Deployment Guide

Production deployment on Ubuntu 24.04 LTS. Assumes a single central server for the Laravel app, Postgres, and the main crawler worker, with an optional second host in Japan for geo-routed adapters.

---

## 1. Server requirements

| Resource | Minimum | Notes |
|---|---|---|
| CPU | 1 vCPU | Crawler is async I/O-bound, not CPU-bound |
| RAM | 1 GB | 512 MB is tight with PHP-FPM + Python both resident |
| Disk | 10 GB | Listings + snapshots grow over time; plan accordingly |
| OS | Ubuntu 24.04 LTS | Debian 12 also works |
| Postgres | 15+ | Can be on the same host or a managed instance |

---

## 2. System packages

```bash
sudo apt update && sudo apt install -y \
  git curl build-essential \
  python3.12 python3.12-venv python3.12-dev \
  php8.2 php8.2-fpm php8.2-pgsql php8.2-mbstring php8.2-xml php8.2-curl \
  php8.2-zip php8.2-bcmath php8.2-intl \
  postgresql-client \
  nginx certbot python3-certbot-nginx \
  nodejs npm
```

Install Composer:

```bash
curl -sS https://getcomposer.org/installer | php
sudo mv composer.phar /usr/local/bin/composer
```

---

## 3. PostgreSQL

If running Postgres on the same host:

```bash
sudo apt install -y postgresql-16
sudo -u postgres createuser --pwprompt appuser
sudo -u postgres createdb -O appuser bike_parts_watcher
```

If using a managed Postgres instance (Supabase, RDS, etc.) skip the above — just note the connection string.

---

## 4. Application user and directory

```bash
sudo useradd -m -s /bin/bash deploy
sudo mkdir -p /var/www/parts-watcher
sudo chown deploy:deploy /var/www/parts-watcher
sudo -u deploy git clone https://github.com/youruser/yourrepo.git /var/www/parts-watcher
```

---

## 5. Python crawler

```bash
cd /var/www/parts-watcher
sudo -u deploy python3.12 -m venv .venv
sudo -u deploy .venv/bin/pip install -e ".[dev]"

sudo -u deploy cp .env.example .env
sudo -u deploy nano .env          # set DATABASE_URL, source credentials
```

Run migrations and seed once:

```bash
sudo -u deploy bash -c "source .venv/bin/activate && python3 -m alembic upgrade head"
sudo -u deploy bash -c "source .venv/bin/activate && parts-watch init-db"
sudo -u deploy bash -c "source .venv/bin/activate && parts-watch sync-catalog"
```

---

## 6. Laravel console

```bash
cd /var/www/parts-watcher/console
sudo -u deploy composer install --no-dev --optimize-autoloader
sudo -u deploy npm ci && sudo -u deploy npm run build

sudo -u deploy cp .env.example .env
sudo -u deploy nano .env          # set APP_KEY, DB_*, WATCHER_DB_*, ADMIN_*, QUEUE_CONNECTION=database

sudo -u deploy php artisan key:generate
sudo -u deploy php artisan migrate --force
sudo -u deploy php artisan db:seed --force
sudo -u deploy php artisan storage:link

# Production cache (re-run after every deploy)
sudo -u deploy php artisan config:cache
sudo -u deploy php artisan route:cache
sudo -u deploy php artisan view:cache

# Writable directories
sudo chown -R deploy:www-data storage bootstrap/cache
sudo chmod -R 775 storage bootstrap/cache
```

---

## 7. Nginx

Create `/etc/nginx/sites-available/parts-watcher`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    root /var/www/parts-watcher/console/public;
    index index.php;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
    }

    location ~ /\.ht {
        deny all;
    }

    client_max_body_size 20M;   # for bike image uploads
}
```

```bash
sudo ln -s /etc/nginx/sites-available/parts-watcher /etc/nginx/sites-enabled/
sudo certbot --nginx -d yourdomain.com    # obtain TLS cert
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. systemd services

### Laravel queue worker

`/etc/systemd/system/parts-watcher-queue.service`:

```ini
[Unit]
Description=Motorcycle Parts Watcher — Laravel queue worker
After=network.target postgresql.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/parts-watcher/console
ExecStart=/usr/bin/php artisan queue:work database --queue=sync --sleep=3 --tries=1 --timeout=1800
Restart=on-failure
RestartSec=5s
KillSignal=SIGTERM
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Crawler worker (central host)

`/etc/systemd/system/parts-watch-worker.service`:

```ini
[Unit]
Description=Motorcycle Parts Watcher — crawler worker (central)
After=network.target postgresql.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/parts-watcher
Environment="PATH=/var/www/parts-watcher/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/var/www/parts-watcher/.env
ExecStart=/var/www/parts-watcher/.venv/bin/parts-watch worker \
    --worker-id central-1 \
    --adapters ebay,buyee,webike,manual_search,yahoo_auctions,monotaro
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start both:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now parts-watcher-queue
sudo systemctl enable --now parts-watch-worker

# Check status
sudo systemctl status parts-watcher-queue
sudo systemctl status parts-watch-worker
sudo journalctl -u parts-watch-worker -f
```

---

## 9. Scheduler cron

```bash
sudo -u deploy crontab -e
```

Add:

```
* * * * * cd /var/www/parts-watcher/console && php artisan schedule:run >> /dev/null 2>&1
```

This fires the scheduler every minute; the scheduler decides which jobs are due (hourly `crawl-all` and `crawl-watches`).

---

## 10. Optional — JP worker on a remote host

For geo-restricted adapters (Yahoo Auctions JP, Webike JP, etc.) that require a Japanese IP:

### On the central host — set up WireGuard

```bash
sudo apt install wireguard
# generate keys, configure wg0.conf to accept the JP peer
# expose only port 5432 internally — never publicly
```

### On the JP host

```bash
# Install WireGuard, connect to central host's private network
# Install Python + venv same as §5
git clone https://github.com/youruser/yourrepo.git /var/www/parts-watcher
cd /var/www/parts-watcher
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# .env points DATABASE_URL at the central Postgres over the WireGuard tunnel
echo "DATABASE_URL=postgresql+psycopg://appuser:pass@10.0.0.1:5432/bike_parts_watcher" > .env
echo "DB_SCHEMA=watcher" >> .env
```

Create `/etc/systemd/system/parts-watch-worker-jp.service` on the JP host:

```ini
[Unit]
Description=Motorcycle Parts Watcher — crawler worker (JP)
After=network.target wg-quick@wg0.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/parts-watcher
Environment="PATH=/var/www/parts-watcher/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/var/www/parts-watcher/.env
ExecStart=/var/www/parts-watcher/.venv/bin/parts-watch worker \
    --worker-id jp-1 \
    --adapters webike_jp,yahoo_auctions,mercari,monotaro,rakuten,goobike
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now parts-watch-worker-jp
```

The JP worker shares the same `watcher.crawl_jobs` queue. The producer on the central host enqueues jobs for all adapters; each worker claims only the jobs matching its `--adapters` list via `FOR UPDATE SKIP LOCKED`.

---

## 11. Deploying updates

```bash
cd /var/www/parts-watcher
sudo -u deploy git pull

# Python — reinstall if dependencies changed
sudo -u deploy .venv/bin/pip install -e "."

# Run any new migrations
sudo -u deploy bash -c "source .venv/bin/activate && python3 -m alembic upgrade head"

# Laravel
cd console
sudo -u deploy composer install --no-dev --optimize-autoloader
sudo -u deploy npm ci && sudo -u deploy npm run build
sudo -u deploy php artisan migrate --force
sudo -u deploy php artisan config:cache
sudo -u deploy php artisan route:cache
sudo -u deploy php artisan view:cache

# Restart services
sudo systemctl restart parts-watcher-queue
sudo systemctl restart parts-watch-worker
```

---

## 12. Monitoring

```bash
# Queue health
source /var/www/parts-watcher/.venv/bin/activate
parts-watch jobs                   # counts by status × adapter
parts-watch jobs --stuck           # rows locked by a dead worker

# Release stale locks after a crashed worker
parts-watch jobs --release-stale

# Clean up old completed/failed rows
parts-watch jobs --prune --older-than-days 7

# Service logs
sudo journalctl -u parts-watcher-queue  -n 100 --no-pager
sudo journalctl -u parts-watch-worker   -n 100 --no-pager

# Postgres sizes
psql -d bike_parts_watcher -c "
  SELECT schemaname, tablename,
         pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname IN ('watcher','console')
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```
