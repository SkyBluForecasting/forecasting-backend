#!/bin/bash
echo "$(date): Cleaning old temp files and directories..."

# Delete all tmp* directories immediately
rm -rf /tmp/tmp*

echo "$(date): Cleaning Docker system..."

# Remove stopped containers, unused images, volumes, and build cache
docker system prune -a --volumes -f
docker builder prune -a -f

echo "$(date): Cleanup complete."
