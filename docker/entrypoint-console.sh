#!/bin/sh
set -e

# Ensure writable storage dirs exist on a fresh named volume
mkdir -p storage/framework/cache/data storage/framework/sessions \
         storage/framework/views storage/logs bootstrap/cache
chmod -R 775 storage bootstrap/cache

exec "$@"
