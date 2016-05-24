#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source $DIR/utils.sh

if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME="hqservice"
fi

FLAVOUR="services"
create_kafka_topics
