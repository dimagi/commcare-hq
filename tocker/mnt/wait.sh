#!/bin/bash

set -e

if [ -n "$1" ]; then
    SERVICES="$1"
else [ -n "DEPENDENT_SERVICES" ]
    SERVICES="$DEPENDENT_SERVICES"
fi
if [ -z "$SERVICES" ]; then
    exit 0
fi

echo "Waiting for services: $SERVICES"

for service in $SERVICES; do
    while [ -z "$host" ]; do
        svc=$(echo $service | tr '[:lower:]' '[:upper:]')
        host=$(env | grep -E "${svc}_PORT_[0-9]+_TCP_ADDR" | cut -d = -f 2 | head -n1)
        port=$(env | grep -E "${svc}_PORT_[0-9]+_TCP_PORT" | cut -d = -f 2 | head -n1)

        [ -z "$host" ] && echo "Waiting for link to $service" && sleep 1
    done

    echo -n "Waiting for TCP connection to $service @ $host:$port..."

    while ! { exec 6<>/dev/tcp/${host}/${port}; } 2>/dev/null
    do
      echo -n .
      sleep 1
    done

    echo "$service ok"
    host=
done

echo "Services ready: $SERVICES"
