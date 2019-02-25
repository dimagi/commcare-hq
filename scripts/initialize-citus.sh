#!/usr/bin/env bash
set -e

DATABASE=commcarehq_citus_ucr

function exec_sql() {
    HOST=$1
    DB=$2
    SQL=$3
    docker exec -it $HOST psql -U commcarehq $DB -c "$SQL"
}

function get_worker_status() {
    echo "`docker inspect -f {{.State.Health.Status}} citus_worker_1`"
}

COMPOSE_PROJECT_NAME=citus docker-compose -f docker/citus-compose.yml up -d

MAX_ATTEMPTS=10
ATTEMPTS=0
until [[ "`get_worker_status`" == "healthy" || $ATTEMPTS -eq $MAX_ATTEMPTS ]]; do
    echo "Waiting for worker. Attempt $((ATTEMPTS++))"
    sleep 1;
done;

if [ "`get_worker_status`" != "healthy" ]; then
    echo "Citus worker not healthy: `get_worker_status`"
    echo $ATTEMPTS
    exit 1
fi

exec_sql citus_master $DATABASE "select * from master_get_active_worker_nodes();"