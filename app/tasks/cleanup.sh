#!/bin/bash

# Absolute paths for commands
DATE_CMD="/bin/date"
RM_CMD="/bin/rm"
DOCKER_CMD="/usr/bin/docker"

# Log start
echo "$($DATE_CMD): Cleaning old temp files and directories..."

# Delete all tmp* directories in /tmp
$RM_CMD -rf /tmp/tmp*

echo "$($DATE_CMD): Cleaning Docker system..."

# Remove stopped containers, unused images, volumes, and build cache
# Use absolute path to docker
$DOCKER_CMD system prune -a --volumes -f
$DOCKER_CMD builder prune -a -f

echo "$($DATE_CMD): Cleanup complete."
