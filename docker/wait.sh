#!/bin/bash

set -e

SERVICES="REDIS COUCH POSTGRES"
if [ -n "$1" ]; then
    SERVICES="$1"
else [ -n "DEPENDENT_SERVICES" ]
    SERVICES="$DEPENDENT_SERVICES"
fi

echo "Services: $SERVICES"

for service in $SERVICES; do
    while [ -z "$host" ]; do
        host=$(env | grep $service | grep _TCP_ADDR | cut -d = -f 2 | head -n1)
        port=$(env | grep $service | grep _TCP_PORT | cut -d = -f 2 | head -n1)

        [ -z "$host" ] && echo "Waiting for link to $service" && sleep 1
    done

    echo -n "Waiting for TCP connection to $service @ $host:$port..."

    while ! exec 6<>/dev/tcp/${host}/${port}
    do
      echo -n .
      sleep 1
    done

    echo "$service ok"
    #reset host
    host=
done

echo "ALL SERVICES READY"
