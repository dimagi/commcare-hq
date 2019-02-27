#!/usr/bin/env bash
set -e

NETWORK=${1:-}

DATABASE=postgres

function exec_sql() {
    HOST=$1
    DB=$2
    SQL=$3
    docker exec -it $HOST psql -U postgres $DB -c "$SQL"
}

COMPOSE_PROJECT_NAME=citus docker-compose -f docker/citus-compose.yml up -d

exec_sql citus_master $DATABASE "select * from master_get_active_worker_nodes();"

if [ !  -z  $NETWORK  ]; then
    # Connecting the coordinator to the HQ docker network allows the containers
    # in that network to reach the coordinator and to resolve 'citus_master' to
    # the correct IP
    echo "Connecting citus_master to '$NETWORK' network"
    docker network connect $NETWORK citus_master
fi