#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ES_CLUSTER_NAME=$(hostname)
PROJECT_NAME=hqservice

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
    sudo \
        env ES_CLUSTER_NAME=$ES_CLUSTER_NAME \
        docker-compose -f $DIR/docker-compose-services.yml -p $PROJECT_NAME $@
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
            runner $key
            exit
            ;;
        logs)
            runner logs $2
            exit
            ;;
        *)
            echo "ERROR: unknown parameter \"$PARAM\""
            usage
            exit 1
            ;;
    esac
    shift
done
