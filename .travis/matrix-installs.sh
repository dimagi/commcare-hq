#!/bin/bash
set -ev

source .travis/utils.sh

echo "Matrix params: MATRIX_TYPE=${MATRIX_TYPE:?Empty value for MATRIX_TYPE}, BOWER=${BOWER:-no}"

if [ "${MATRIX_TYPE}" = "python" ]; then
    pip install --exists-action w --timeout 60 --requirement=requirements/test-requirements.txt

    setup_elasticsearch
    setup_kafka
elif [ "${MATRIX_TYPE}" = "javascript" ]; then
    npm install -g grunt
    npm install -g grunt-cli
    npm install
else
    echo "Unknown value MATRIX_TYPE=$MATRIX_TYPE. Allowed values are 'python', 'javascript'"
    exit 1
fi

if [ "${BOWER:-no}" = "yes" ]; then
    npm install -g uglify-js
    npm install -g bower
    bower install
fi

if [ "${NODE:-no}" = "yes" ]; then
    npm install
fi
