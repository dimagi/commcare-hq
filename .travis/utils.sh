#!/usr/bin/env bash

TRAVIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

travis_runner() {
    args=$@

    flavour='travis'
    if [ "${MATRIX_TYPE}" = "javascript" ]; then
        flavour='travis-js'
    fi

    $TRAVIS_DIR/../dockerhq.sh $flavour run --rm $args
}

get_container_id() {
    label_name=$1
    value=$2
    sudo docker ps -fq label=$label_name=$value -f status=running
}

get_container_ip() {
    CID=$(get_container_id $@)
    sudo docker inspect --format '{{ .NetworkSettings.IPAddress }}' ${CID} | tr -d '\n' | tr -d '\r'
}

create_topics() {
    topics_script=$1
    zookeeper_ip=$2
    topics=$3

    for topic in $topics; do
        travis_runner kafka $topics_script --create --partitions 1 --replication-factor 1 --zookeeper $zookeeper_ip:2181 --topic $topic
    done
}

setup_kafka() {
    kafka_topics=$(travis_runner kafka find /opt -name kafka-topics.sh | tr -d '\n' | tr -d '\r')
    zookeeper_ip=$(get_container_ip "commcare.name" "kafka")
    create_topics $kafka_topics $zookeeper_ip "case form meta case-sql form-sql"
}
