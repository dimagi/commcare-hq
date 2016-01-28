#!/bin/bash
set -ev

source .travis/utils.sh

if [ "${MATRIX_TYPE}" = "python" ]; then
    command="coverage run manage.py test --noinput --failfast --traceback --verbosity=2 --testrunner=$TESTRUNNER"
    travis_runner web_test $command
elif [ "${MATRIX_TYPE}" = "python-sharded" ]; then
    command="coverage run manage.py test --noinput --failfast --traceback --verbosity=2 form_processor"
    travis_runner -e USE_PARTITIONED_DATABASE=yes web_test $command
elif [ "${MATRIX_TYPE}" = "javascript" ]; then
    travis_runner web_test python manage.py migrate --noinput
    travis_runner web_test grunt mocha
fi
