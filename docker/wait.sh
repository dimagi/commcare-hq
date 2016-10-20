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
    svc=$(echo $service | cut -d : -f 1)
    port=$(echo $service | cut -d : -f 2)
    while [ -z "$host" ]; do
        host=$(env | grep -E "${svc}_PORT_${port}_TCP_ADDR" | cut -d = -f 2 | head -n1)

        [ -z "$host" ] && echo "Waiting for link to $svc" && sleep 1
    done

    echo -n "Waiting for TCP connection to $svc @ $host:$port..."

    counter=0
    while ! { exec 6<>/dev/tcp/${host}/${port}; } 2>/dev/null
    do
      echo -n .
      sleep 1
      let counter=counter+1
      if [ $counter -gt 90 ]; then
        echo "TIMEOUT"
        exit 1
      fi
    done

    echo "$svc ok"
    host=
done

echo "Services ready!"
