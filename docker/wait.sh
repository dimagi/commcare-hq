#!/bin/bash

set -e

PREFIX=$(env | grep REDIS_NAME | cut -d / -f 2 | cut -d _ -f 1 | awk '{print toupper($0)}')
SERVICES="REDIS ELASTICSEARCH COUCH POSTGRES"

for service in $SERVICES; do
    while [ -z "$host" ]; do
        host=$(env | grep $service | grep $PREFIX | grep _TCP_ADDR | cut -d = -f 2 | head -n1)
        port=$(env | grep $service | grep $PREFIX | grep _TCP_PORT | cut -d = -f 2 | head -n1)
    done

    echo -n "waiting for TCP connection to $service @ $host:$port..."

    while ! exec 6<>/dev/tcp/${host}/${port}
    do
      echo -n .
      sleep 1
    done

    echo "$service ok"
done

echo "ALL SERVICES READY"
