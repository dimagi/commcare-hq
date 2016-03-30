#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source $DIR/utils.sh

FLAVOUR="services"
create_kafka_topics
