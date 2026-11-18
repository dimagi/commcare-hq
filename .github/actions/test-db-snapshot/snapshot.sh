#!/usr/bin/env bash
# Save or restore a snapshot of the test databases in the hqtest postgres
# container. Used by action.yml in this directory.
#
#   snapshot.sh save DIR
#       Dump each database named *_snapshot to DIR/<name>.dump, where
#       <name> is the name without the suffix. `pytest --snapshot-test-dbs`
#       creates those copies right after it creates the test databases,
#       before any test runs.
#
#   snapshot.sh restore DIR
#       Start postgres and restore each DIR/<name>.dump as database <name>.
#       Tests run with --reusedb=1 then find the databases and skip setup.
#       Each database gets its final name only once its restore succeeds,
#       so after a failure the tests set up the missing databases as usual.
set -euo pipefail
shopt -s nullglob

CONTAINER=hqtest-postgres-1
PG_USER=commcarehq

function save {
    local snapshots
    rm -rf "$1"
    mkdir -p "$1"
    snapshots=$(sql "SELECT datname FROM pg_database WHERE datname LIKE '%\_snapshot'")
    for snapshot in $snapshots; do
        echo "Dumping $snapshot"
        docker exec "$CONTAINER" pg_dump -U "$PG_USER" --format=custom "$snapshot" \
            > "$1/${snapshot%_snapshot}.dump"
    done
}

function restore {
    scripts/docker hqtest up --detach postgres
    # Check over TCP: during first-time init the postgres image runs a
    # temporary server that only listens on the unix socket.
    timeout 60 bash -c "until docker exec $CONTAINER pg_isready -q -h 127.0.0.1 -U $PG_USER; do sleep 1; done"
    for dump in "$1"/*.dump; do
        local name
        name=$(basename "$dump" .dump)
        echo "Restoring $name"
        sql "CREATE DATABASE \"${name}_restoring\""
        docker exec -i "$CONTAINER" pg_restore -U "$PG_USER" --exit-on-error \
            --dbname="${name}_restoring" < "$dump"
        sql "ALTER DATABASE \"${name}_restoring\" RENAME TO \"$name\""
    done
}

function sql {
    docker exec "$CONTAINER" psql -U "$PG_USER" --dbname=postgres \
        --no-align --tuples-only --command="$1"
}

case "${1:-}" in
    save|restore) "$1" "$2" ;;
    *) echo "usage: $0 save|restore DIR" >&2; exit 2 ;;
esac
