#!/bin/bash
set -ev

source .travis/utils.sh

run_tests() {
    # This function allows overriding the test comnmand and the test that get run
    # which is used by 'simulate.sh'
    TESTS=${TEST_OVERRIDE:-"$1"}

    ENV_VARS=""
    if [ $# -eq 2 ]; then
        ENV_VARS="$2"
    fi

    if [ -z ${COMMAND_OVERRIDE} ]; then
        travis_runner $ENV_VARS web_test ".travis/test_runner.sh $TESTS"
    else
        travis_runner $ENV_VARS web_test $COMMAND_OVERRIDE
    fi

}
if [ "${MATRIX_TYPE}" = "python" ]; then
    TESTS="--testrunner=$TESTRUNNER"
    run_tests "$TESTS"

elif [ "${MATRIX_TYPE}" = "python-sharded" ]; then

    SHARDED_TEST_APPS="form_processor sql_db couchforms case phone receiverwrapper"
    ENV="-e USE_PARTITIONED_DATABASE=yes"
    run_tests "$SHARDED_TEST_APPS" "$ENV"

elif [ "${MATRIX_TYPE}" = "javascript" ]; then

    travis_runner web_test python manage.py migrate --noinput
    travis_runner web_test docker/wait.sh WEB_TEST
    travis_runner web_test grunt mocha

fi
