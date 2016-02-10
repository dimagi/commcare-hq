#!/bin/bash
set -ev

source .travis/utils.sh

if [ "${MATRIX_TYPE}" = "python" ] || [ "${MATRIX_TYPE}" = "python-sharded" ]; then

    ./dockerhq.sh travis build
    ./dockerhq.sh travis up -d
    ./dockerhq.sh travis ps

elif [ "${MATRIX_TYPE}" = "javascript" ]; then

    ./dockerhq.sh travis-js build
    ./dockerhq.sh travis-js up -d
    ./dockerhq.sh travis-js ps

fi
