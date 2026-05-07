#!/bin/sh
set -e

# Ensure writable storage dirs exist on a fresh named volume
mkdir -p storage/framework/cache/data storage/framework/sessions \
         storage/framework/views storage/logs bootstrap/cache \
         public/bike-images
chown -R www-data:www-data storage bootstrap/cache public/bike-images
chmod -R 775 storage bootstrap/cache public/bike-images

# Install / update PHP deps when composer.lock has changed since the last run.
# vendor/ lives in a named volume so it persists across restarts.
LOCK_HASH=$(md5sum composer.lock 2>/dev/null | cut -d' ' -f1 || echo "none")
STORED_HASH=$(cat vendor/.composer-lock-hash 2>/dev/null || echo "")

if [ "$LOCK_HASH" != "$STORED_HASH" ]; then
    echo "[entrypoint] composer.lock changed — running composer install..."
    composer install --no-dev --no-interaction --no-scripts --optimize-autoloader
    echo "$LOCK_HASH" > vendor/.composer-lock-hash
fi

exec "$@"
