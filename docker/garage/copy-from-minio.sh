#!/usr/bin/env bash
# Copy blobs from local MinIO into Garage. Safe to rerun: rclone only copies
# objects that are new or changed, and nothing is deleted from MinIO.
#
# If the MinIO container isn't running (e.g. MinIO has been removed from the
# compose files), a temporary MinIO is started on its old data directory.
set -euo pipefail

NETWORK=${NETWORK:-hqservice_default}
MINIO_CONTAINER=${MINIO_CONTAINER:-hqservice-minio-1}
MINIO_DATA=${MINIO_DATA:-${XDG_DATA_HOME:-$HOME/.local/share}/dockerhq/minio-data}
GARAGE_CONTAINER=${GARAGE_CONTAINER:-hqservice-garage-1}
BUCKET=blobdb

running() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]; }

if ! running "$GARAGE_CONTAINER"; then
    echo "Garage is not running. Start it with: ./scripts/docker up -d garage" >&2
    exit 1
fi

if ! running "$MINIO_CONTAINER"; then
    if [ ! -d "$MINIO_DATA/$BUCKET" ]; then
        echo "MinIO is not running and there is no MinIO data at $MINIO_DATA" >&2
        exit 1
    fi
    MINIO_CONTAINER=hq-minio-migration
    echo "Starting a temporary MinIO on $MINIO_DATA"
    # left behind if an earlier run was killed before its cleanup ran
    docker rm -f "$MINIO_CONTAINER" >/dev/null 2>&1 || true
    # the image is amd64-only; see docker/hq-compose-os-macos-m1-12.yml
    docker run -d --rm --name "$MINIO_CONTAINER" --network "$NETWORK" \
        --platform linux/amd64 -v "$MINIO_DATA:/data" \
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
        -e RCLONE_CONFIG_MINIO_ENDPOINT="http://$MINIO_CONTAINER:9980" \
        -e RCLONE_CONFIG_MINIO_ACCESS_KEY_ID=admin-key \
        -e RCLONE_CONFIG_MINIO_SECRET_ACCESS_KEY=admin-secret \
        -e RCLONE_CONFIG_GARAGE_TYPE=s3 \
        -e RCLONE_CONFIG_GARAGE_PROVIDER=Other \
        -e RCLONE_CONFIG_GARAGE_ENDPOINT="http://$GARAGE_CONTAINER:3900" \
        -e RCLONE_CONFIG_GARAGE_REGION=us-east-1 \
        -e RCLONE_CONFIG_GARAGE_FORCE_PATH_STYLE=true \
        -e RCLONE_CONFIG_GARAGE_ACCESS_KEY_ID=GK31c2f218a2e44f485b94239e \
        -e RCLONE_CONFIG_GARAGE_SECRET_ACCESS_KEY=b892c0665f0ada8a4755dae98baa3b133590e11dae3bcc1f9d2d1d12b6c1cb2b \
        docker.io/rclone/rclone:1.75.1 --config "" "$@"
}

rclone copy "minio:$BUCKET" "garage:$BUCKET" --checksum --transfers 16 --stats-one-line --stats 10s
rclone check --one-way "minio:$BUCKET" "garage:$BUCKET"
