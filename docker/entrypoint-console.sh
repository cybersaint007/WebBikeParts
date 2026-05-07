#!/bin/sh
set -e

# Ensure writable storage dirs exist on a fresh named volume
mkdir -p storage/framework/cache/data storage/framework/sessions \
         storage/framework/views storage/logs bootstrap/cache \
         public/bike-images
chown -R www-data:www-data storage bootstrap/cache public/bike-images
chmod -R 775 storage bootstrap/cache public/bike-images

exec "$@"
