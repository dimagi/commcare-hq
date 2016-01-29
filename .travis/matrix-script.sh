#!/bin/bash
set -ev

source .travis/utils.sh

if [ "${MATRIX_TYPE}" = "python" ]; then

    COMMAND="coverage run manage.py test --noinput --failfast --traceback --verbosity=2"
    TESTS=${TEST_OVERRIDE:-"--testrunner=$TESTRUNNER"}
    travis_runner web_test $COMMAND $TESTS

elif [ "${MATRIX_TYPE}" = "python-sharded" ]; then

    SHARDED_TEST_APPS="form_processor sql_db couchforms case phone receiverwrapper"
    COMMAND="coverage run manage.py test --noinput --failfast --traceback --verbosity=2 $SHARDED_TEST_APPS"
    travis_runner -e USE_PARTITIONED_DATABASE=yes web_test $COMMAND

elif [ "${MATRIX_TYPE}" = "javascript" ]; then

    travis_runner web_test python manage.py migrate --noinput
    travis_runner web_test docker/wait.sh WEB_TEST
    travis_runner web_test grunt mocha

fi
