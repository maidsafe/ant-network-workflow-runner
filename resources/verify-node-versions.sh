#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <environment-name> <antctl-version> <antnode-version> <branch>"
  exit 1
fi
if [ -z "$2" ]; then
  echo "Usage: $0 <environment-name> <antctl-version> <antnode-version> <branch>"
  exit 1
fi
if [ -z "$3" ]; then
  echo "Usage: $0 <environment-name> <antctl-version> <antnode-version> <branch>"
  exit 1
fi
if [ -z "$4" ]; then
  echo "Usage: $0 <environment-name> <antctl-version> <antnode-version> <branch>"
  exit 1
fi

ENVIRONMENT="$1"
EXPECTED_ANTCTL_VERSION="$2"
EXPECTED_ANTNODE_VERSION="$3"
EXPECTED_BRANCH="$4"

DROPLET_PREFIX="${ENVIRONMENT}-node"
ANTNODE_PATH="/mnt/antnode-storage/data/antnode1/antnode"

IP_ADDRESSES=($(doctl \
  compute droplet list --format Name,PublicIPv4 --no-header | \
  awk -v prefix="$DROPLET_PREFIX" '$1 ~ "^"prefix {print $2}' | \
  head -n 5))

if [ ${#IP_ADDRESSES[@]} -eq 0 ]; then
  echo "No droplets found matching prefix: $DROPLET_PREFIX"
  exit 1
fi

for IP in "${IP_ADDRESSES[@]}"; do
  antctl_version=$( \
    ssh -o StrictHostKeyChecking=no \
    root@$IP "antctl --version | grep -oP 'Autonomi Node Manager \K\S+'")
  antctl_branch=$(ssh -o StrictHostKeyChecking=no root@$IP "antctl --version | grep -oP 'Git info: \K\S+'")

  if [[ "$antctl_version" == "$EXPECTED_ANTCTL_VERSION" ]]; then
    echo "$IP matches $EXPECTED_ANTCTL_VERSION"
  else
    echo "TEST FAILED!!!"
    echo "antctl version on $IP did not match the expected version"
    exit 1
  fi
  if [[ "$antctl_branch" == "$EXPECTED_BRANCH" ]]; then
    echo "$IP matches $EXPECTED_BRANCH"
  else
    echo "TEST FAILED!!!"
    echo "antctl branch on $IP did not match the expected branch"
    exit 1
  fi

  antnode_version=$( \
    ssh -o StrictHostKeyChecking=no \
    root@$IP "$ANTNODE_PATH --version | grep -oP 'Autonomi Node \K\S+'")
  antnode_branch=$(\
    ssh -o StrictHostKeyChecking=no root@$IP "$ANTNODE_PATH --version | grep -oP 'Git info: \K\S+'")

  if [[ "$antnode_version" == "$EXPECTED_ANTNODE_VERSION" ]]; then
    echo "$IP matches $EXPECTED_ANTNODE_VERSION"
  else
    echo "TEST FAILED!!!"
    echo "antnode version on $IP did not match the expected version"
    exit 1
  fi
  if [[ "$antnode_branch" == "$EXPECTED_BRANCH" ]]; then
    echo "$IP matches $EXPECTED_BRANCH"
  else
    echo "TEST FAILED!!!"
    echo "antnode version on $IP did not match the expected version"
    exit 1
  fi
done
