#!/usr/bin/env bash
set -e

DATABASE=postgres

function exec_sql() {
    HOST=$1
    DB=$2
    SQL=$3
    docker exec -it $HOST psql -U postgres $DB -c "$SQL"
}

COMPOSE_PROJECT_NAME=citus docker-compose -f docker/citus-compose.yml up -d

exec_sql citus_master $DATABASE "select * from master_get_active_worker_nodes();"