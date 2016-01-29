#!/usr/bin/env bash

. $(dirname "$0")/_include.sh

$DOCKER_DIR/docker-services.sh start

web_runner run web /mnt/docker/bootstrap_internal.sh

