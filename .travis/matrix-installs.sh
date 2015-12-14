#!/bin/bash
set -ev

source .travis/utils.sh

echo "Matrix params: MATRIX_TYPE=${MATRIX_TYPE:?Empty value for MATRIX_TYPE}, BOWER=${BOWER:-no}"

if [ "${MATRIX_TYPE}" = "python" ]; then
    pip install coverage unittest2 mock

    install_elasticsearch
    # kafka install, copied from https://github.com/wvanbergen/kafka/blob/master/.travis.yml
    wget http://www.us.apache.org/dist/kafka/0.8.2.1/kafka_2.10-0.8.2.1.tgz -O kafka.tgz
    mkdir -p kafka && tar xzf kafka.tgz -C kafka --strip-components 1
    nohup bash -c "cd kafka && bin/zookeeper-server-start.sh config/zookeeper.properties &"
    nohup bash -c "cd kafka && bin/kafka-server-start.sh config/server.properties &"
    sleep 5
    kafka/bin/kafka-topics.sh --create --partitions 1 --replication-factor 1 --topic case --zookeeper localhost:2181
elif [ "${MATRIX_TYPE}" = "javascript" ]; then
    npm install -g grunt
    npm install -g grunt-cli
    npm install
else
    echo "Unknown value MATRIX_TYPE=$MATRIX_TYPE. Allowed values are 'python', 'javascript'"
    exit 1
fi

if [ "${BOWER:-no}" = "yes" ]; then
    npm install -g bower
    bower install
fi
