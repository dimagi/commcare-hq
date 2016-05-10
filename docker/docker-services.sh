#!/usr/bin/env bash

. $(dirname "$0")/_include.sh

ES_CLUSTER_NAME=$(hostname)
PROJECT_NAME=hqservice
if [ `uname` == 'Darwin' -a "$DOCKER_BETA" != "true" ]; then
    # use boot2docker host ip
    KAFKA_ADVERTISED_HOST_NAME=$(docker-machine ip $DOCKER_MACHINE_NAME)
else
    KAFKA_ADVERTISED_HOST_NAME=localhost
fi

function usage() {
    echo "Helper script to start and stop services for CommCare HQ"
    echo ""
    echo "./docker-services.sh [OPTIONS] COMMAND"
    echo "      -h --help"
    echo "      --es-cluster-name $ES_CLUSTER_NAME"
    echo "      start|stop|down|logs [SERVICE]"
    echo ""
}

function runner() {
    $UDO \
        env ES_CLUSTER_NAME=$ES_CLUSTER_NAME \
        KAFKA_ADVERTISED_HOST_NAME=$KAFKA_ADVERTISED_HOST_NAME \
        DOCKER_DATA_HOME=$DOCKER_DATA_HOME \
        docker-compose -f $DOCKER_DIR/compose/docker-compose-services.yml -p $PROJECT_NAME $@
}

while [[ $# > 0 ]]; do
    key="$1"

    case $key in
        -h | --help)
            usage
            exit
            ;;
        --es-cluster-name)
            ES_CLUSTER_NAME="$2"
            shift
            ;;
        start)
            runner up -d
            exit
            ;;
        stop | down)
            shift
            runner $key $@
            exit
            ;;
        logs)
            runner logs $2
            exit
            ;;
        *)
            runner $@
            exit
            ;;
    esac
    shift
done
