#!/usr/bin/env bash
# Script to simulate travis
# Usage:
#   simulate.sh [MATRIX] [TEST_OVERRIDE]
#
#   MATRIX:         test matrix to run
#                   One of javascript, python_catchall, python_group_0, python_sharded
#   TEST_OVERRIDE:  List of Django test labels to run instead of matrix default
#
# e.g. simulate.sh python_catchall app_manager.SuiteTest

set -e

TRAVIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR=$( dirname "${TRAVIS_DIR}")

LOCALSETTINGS=$BASE_DIR/localsettings.py
LOCALSETTINGS_TMP=$BASE_DIR/localsettings.tmp.py

set_env() {
    export MATRIX_TYPE=$1
    export TESTRUNNER=$2
    export BOWER=$3
    export NODE=$4
}

prepare() {
    if [ -f $LOCALSETTINGS_TMP ]; then
        echo "Abort: potential override of localsettings at $LOCALSETTINGS_TMP"
        exit 1
    fi
    mv $LOCALSETTINGS $LOCALSETTINGS_TMP
    cp .travis/localsettings.py $LOCALSETTINGS
}

reset() {
    $BASE_DIR/dockerhq.sh travis down
    $BASE_DIR/dockerhq.sh travis-js down
}

cleanup() {
    [ -f $LOCALSETTINGS_TMP ] && mv $LOCALSETTINGS_TMP $LOCALSETTINGS
    [ -f $BASE_DIR/InsecureTestingKeyStore ] && rm -f $BASE_DIR/InsecureTestingKeyStore
    reset
}

run() {
    prepare
    .travis/matrix-before_install.sh
    .travis/matrix-install.sh
    .travis/matrix-script.sh
    cleanup
}

trap cleanup SIGINT SIGTERM EXIT ERR

MATRIX="$1"

OPTIONS="javascript|python_catchall|python_group_0|python_sharded"

if [ $# -eq 2 ]; then
    export TEST_OVERRIDE="$2"
fi

case $MATRIX in
    -h | --help | help)
        echo "simulate.sh [$OPTIONS]"
        ;;
    javascript)
        set_env javascript "" yes yes
        ;;
    python_catchall)
        set_env python "testrunner.GroupTestRunnerCatchall" yes yes
        ;;
    python_group_0)
        set_env python "testrunner.GroupTestRunner0" yes yes
        ;;
    python_sharded)
        set_env python-sharded "" "" ""
        ;;
    reset)
        reset
        exit
        ;;
    *)
        echo "Unknown option: $MATRIX. Options are: $OPTIONS"
        exit
        ;;
esac

run

exit
