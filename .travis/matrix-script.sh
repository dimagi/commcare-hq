#!/bin/bash
set -ev

source docker/utils.sh

FLAVOUR='travis'
if [ "${MATRIX_TYPE}" = "javascript" ]; then
    FLAVOUR='travis-js'
fi

run_tests() {
    # This function allows overriding the test comnmand and the test that get run
    # which is used by 'simulate.sh'
    TESTS=${TEST_OVERRIDE:-"$1"}

    ENV_VARS=""
    if [ $# -eq 2 ]; then
        ENV_VARS="$2"
    fi

    if [ -z ${COMMAND_OVERRIDE} ]; then
        docker_run $ENV_VARS web_test ".travis/test_runner.sh $TESTS"
    else
        docker_run $ENV_VARS web_test $COMMAND_OVERRIDE
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

    docker_run web_test python manage.py migrate --noinput
    docker_run web_test docker/wait.sh WEB_TEST
    docker_run web_test grunt mocha

fi
