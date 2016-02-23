#!/bin/bash
set -ev

source docker/utils.sh
FLAVOUR='travis'
if [ "${MATRIX_TYPE}" = "javascript" ]; then
    FLAVOUR='travis-js'
fi

echo "Matrix params: MATRIX_TYPE=${MATRIX_TYPE:?Empty value for MATRIX_TYPE}, BOWER=${BOWER:-no}"

if [ "${MATRIX_TYPE}" = "python" ] || [ "${MATRIX_TYPE}" = "python-sharded" ]; then

    sleep 10  # kafka is slow to start up
    create_kafka_topics
    docker_run web_test .travis/misc-setup.sh

elif [ "${MATRIX_TYPE}" = "javascript" ]; then
    echo 'Done'
else
    echo "Unknown value MATRIX_TYPE=$MATRIX_TYPE. Allowed values are 'python', 'javascript'"
    exit 1
fi

if [ "${BOWER:-no}" = "yes" ]; then
    docker_run web_test bower install
fi

if [ "${NODE:-no}" = "yes" ]; then
    docker_run web_test npm install
fi
