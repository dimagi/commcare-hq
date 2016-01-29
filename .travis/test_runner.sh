#!/usr/bin/env bash

set -e

TESTS="$1"
COMMAND="coverage run manage.py test --noinput --failfast --traceback --verbosity=2"

/moto-s3/env/bin/moto_server s3 &

if [ -z ${COMMAND_OVERRIDE} ]; then
    $COMMAND $TESTS
else
    $COMMAND_OVERRIDE
fi
