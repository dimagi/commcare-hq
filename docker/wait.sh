#!/bin/bash
# TODO convert to using docker compose'depends_on' feature with health checks

set -e

if [ -n "$1" ]; then
    # always use argv if provided
    SERVICES="$1"
elif [ -n "$DEPENDENT_SERVICES" ]; then
    # otherwise use DEPENDENT_SERVICES (if present)
    SERVICES="$DEPENDENT_SERVICES"
else
    echo "ERROR: No services to wait for!"
    exit 1
fi

echo "Waiting for services: $SERVICES"

for service in $SERVICES; do
    svc=$(echo $service | cut -d : -f 1)
    port=$(echo $service | cut -d : -f 2)

    echo -n "Waiting for TCP connection to $svc:$port..."

    counter=0
    while ! { exec 6<>/dev/tcp/${svc}/${port}; } 2>/dev/null
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
done

echo "Services ready!"
