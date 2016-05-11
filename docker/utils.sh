#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ `uname` == 'Linux' ]; then
    UDO="sudo"
else
    UDO=""
fi

docker_run() {
    args=$@
    flavour="${FLAVOUR:-travis}"
    $DIR/../dockerhq.sh $flavour run --rm $args
}

get_container_id() {
    label_name=$1
    value=$2
    $UDO docker ps -qf label=$label_name=$value -f status=running
}

get_container_ip() {
    CID=$(get_container_id $@)
    $UDO docker inspect --format '{{ .NetworkSettings.IPAddress }}' ${CID} | tr -d '\n' | tr -d '\r'
}

create_topics() {
    topics_script=$1
    zookeeper_ip=$2
    topics=$3

    for topic in $topics; do
        docker_run kafka $topics_script --create --partitions 1 --replication-factor 1 --zookeeper $zookeeper_ip:2181 --topic $topic
    done
}

create_kafka_topics() {
    kafka_topics=$(docker_run kafka find /opt -name kafka-topics.sh | tr -d '\n' | tr -d '\r')
    zookeeper_ip=$(get_container_ip "commcare.name" "kafka")
    create_topics $kafka_topics $zookeeper_ip "case form meta case-sql form-sql sms domain commcare-user web-user group ledger"
}
