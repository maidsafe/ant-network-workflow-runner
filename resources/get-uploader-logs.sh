#!/bin/bash

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <environment-name> <number-of-uploaders>"
  exit 1
fi

ENVIRONMENT="$1"
NUM_UPLOADERS="$2"
DROPLET_PREFIX="${ENVIRONMENT}-uploader"

IP_ADDRESSES=($(doctl compute droplet list --format Name,PublicIPv4 --no-header | awk -v prefix="$DROPLET_PREFIX" '$1 ~ "^"prefix {print $2}'))

if [ ${#IP_ADDRESSES[@]} -eq 0 ]; then
  echo "No droplets found matching prefix: $DROPLET_PREFIX"
  exit 1
fi

for IP in "${IP_ADDRESSES[@]}"; do
  for ((i=1; i<=NUM_UPLOADERS; i++)); do
    clear
    echo "================================================================"
    echo "Fetching logs from $IP for ant_uploader_$i..."
    echo "================================================================"
    ssh -o StrictHostKeyChecking=no root@$IP "journalctl -u ant_uploader_$i -o cat --no-pager"
    read -p "Proceed to next uploader..."
  done
done
