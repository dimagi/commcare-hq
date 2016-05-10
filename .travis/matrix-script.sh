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
    run_tests --divided-we-run=$NOSE_DIVIDED_WE_RUN

elif [ "${MATRIX_TYPE}" = "python-sharded" ]; then

    SHARDED_TEST_APPS="corehq.form_processor"
    # commented out due to bug that discarded all but first item
    #    corehq.sql_db \
    #    couchforms \
    #    casexml.apps.case \
    #    casexml.apps.phone \
    #    corehq.apps.receiverwrapper"
    ENV="-e USE_PARTITIONED_DATABASE=yes"
    run_tests "$SHARDED_TEST_APPS" "$ENV"

elif [ "${MATRIX_TYPE}" = "javascript" ]; then

    docker_run web_test python manage.py migrate --noinput
    docker_run web_test docker/wait.sh WEB_TEST
    docker_run web_test grunt mocha

fi
