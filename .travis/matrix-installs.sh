#!/bin/bash
set -ev

source .travis/utils.sh

echo "Matrix params: MATRIX_TYPE=${MATRIX_TYPE:?Empty value for MATRIX_TYPE}, BOWER=${BOWER:-no}"

if [ "${MATRIX_TYPE}" = "python" ]; then
    setup_kafka_docker
    travis_runner web_test .travis/misc_setup.sh
elif [ "${MATRIX_TYPE}" = "javascript" ]; then
    echo 'Done'
else
    echo "Unknown value MATRIX_TYPE=$MATRIX_TYPE. Allowed values are 'python', 'javascript'"
    exit 1
fi

if [ "${BOWER:-no}" = "yes" ]; then
    travis_runner web_test bower install
fi

if [ "${NODE:-no}" = "yes" ]; then
    travis_runner web_test npm install
fi
