#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <environment-name> <ant-version> <branch>"
  exit 1
fi
if [ -z "$2" ]; then
  echo "Usage: $0 <environment-name> <ant-version> <branch>"
  exit 1
fi
if [ -z "$3" ]; then
  echo "Usage: $0 <environment-name> <ant-version> <branch>"
  exit 1
fi

ENVIRONMENT="$1"
EXPECTED_ANT_VERSION="$2"
EXPECTED_BRANCH="$3"

DROPLET_PREFIX="${ENVIRONMENT}-uploader"

IP_ADDRESSES=($(doctl \
  compute droplet list --format Name,PublicIPv4 --no-header | \
  awk -v prefix="$DROPLET_PREFIX" '$1 ~ "^"prefix {print $2}' | \
  head -n 5))

if [ ${#IP_ADDRESSES[@]} -eq 0 ]; then
  echo "No droplets found matching prefix: $DROPLET_PREFIX"
  exit 1
fi

for IP in "${IP_ADDRESSES[@]}"; do
  ant_version=$( \
    ssh -o StrictHostKeyChecking=no \
    root@$IP "ant --version | grep -oP 'Autonomi Client \K\S+'")
  ant_branch=$(ssh -o StrictHostKeyChecking=no root@$IP "ant --version | grep -oP 'Git info: \K\S+'")

  if [[ "$ant_version" == "$EXPECTED_ANT_VERSION" ]]; then
    echo "$IP matches $EXPECTED_ANT_VERSION"
  else
    echo "ant version on $IP did not match the expected version"
    exit 1
  fi
  if [[ "$ant_branch" == "$EXPECTED_BRANCH" ]]; then
    echo "$IP matches $EXPECTED_BRANCH"
  else
    echo "ant branch on $IP did not match the expected branch"
    exit 1
  fi
done
