#!/usr/bin/env bash
# Copy blobs from local MinIO into Garage. Safe to rerun: rclone only copies
# objects that are new or changed, and nothing is deleted from MinIO.
#
# If the MinIO container isn't running (e.g. MinIO has been removed from the
# compose files), a temporary MinIO is started on its old data directory.
set -euo pipefail

PROJECT=${COMPOSE_PROJECT_NAME:-hqservice}
NETWORK=${NETWORK:-${PROJECT}_default}
MINIO_DATA=${MINIO_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/dockerhq/minio-data}
# GARAGE_DEFAULT_BUCKET in docker/hq-compose.yml
BUCKET=blobdb

# Look up containers by compose labels rather than name, because Docker
# Compose names them hqservice-minio-1 and podman-compose hqservice_minio_1.
# rclone reaches them by service name on the compose network.
running() {
    [ -n "$(docker ps -q \
        --filter "label=com.docker.compose.project=$PROJECT" \
        --filter "label=com.docker.compose.service=$1")" ]
}

if ! running garage; then
    echo "Garage is not running. Start it with: ./scripts/docker up -d garage" >&2
    exit 1
fi

if ! running minio; then
    if [ ! -d "$MINIO_DATA/$BUCKET" ]; then
        echo "MinIO is not running and there is no MinIO data at $MINIO_DATA" >&2
        exit 1
    fi
    MINIO_CONTAINER=hq_minio_migration
    echo "Starting a temporary MinIO on $MINIO_DATA"
    # left behind if an earlier run was killed before its cleanup ran
    docker rm -f "$MINIO_CONTAINER" >/dev/null 2>&1 || true
    # The alias lets rclone reach it as "minio", like the compose service.
    docker run -d --rm --name "$MINIO_CONTAINER" \
        --network "$NETWORK" --network-alias minio -v "$MINIO_DATA:/data" \
        -e MINIO_ROOT_USER=admin-key -e MINIO_ROOT_PASSWORD=admin-secret \
        docker.io/dimagi/minio server --address :9980 /data >/dev/null
    trap 'docker stop "$MINIO_CONTAINER" >/dev/null' EXIT
    ready=""
    for _ in $(seq 60); do
        if docker exec "$MINIO_CONTAINER" \
                curl -sf http://127.0.0.1:9980/minio/health/ready >/dev/null 2>&1; then
            ready=1
            break
        fi
        sleep 1
    done
    if [ -z "$ready" ]; then
        echo "Temporary MinIO did not become ready within 60 seconds" >&2
        exit 1
    fi
fi

rclone() {
    # Garage keys match GARAGE_DEFAULT_* in docker/hq-compose.yml
    docker run --rm --network "$NETWORK" \
        -e RCLONE_CONFIG_MINIO_TYPE=s3 \
        -e RCLONE_CONFIG_MINIO_PROVIDER=Minio \
        -e RCLONE_CONFIG_MINIO_ENDPOINT=http://minio:9980 \
        -e RCLONE_CONFIG_MINIO_ACCESS_KEY_ID=admin-key \
        -e RCLONE_CONFIG_MINIO_SECRET_ACCESS_KEY=admin-secret \
        -e RCLONE_CONFIG_GARAGE_TYPE=s3 \
        -e RCLONE_CONFIG_GARAGE_PROVIDER=Other \
        -e RCLONE_CONFIG_GARAGE_ENDPOINT=http://garage:3900 \
        -e RCLONE_CONFIG_GARAGE_REGION=us-east-1 \
        -e RCLONE_CONFIG_GARAGE_FORCE_PATH_STYLE=true \
        -e RCLONE_CONFIG_GARAGE_ACCESS_KEY_ID=GK31c2f218a2e44f485b94239e \
        -e RCLONE_CONFIG_GARAGE_SECRET_ACCESS_KEY=b892c0665f0ada8a4755dae98baa3b133590e11dae3bcc1f9d2d1d12b6c1cb2b \
        docker.io/rclone/rclone:1.75.1 --config "" "$@"
}

rclone copy "minio:$BUCKET" "garage:$BUCKET" --checksum --transfers 16 --stats-one-line --stats 10s
rclone check --one-way "minio:$BUCKET" "garage:$BUCKET"
