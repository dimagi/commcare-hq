#!/usr/bin/env bash
# Script to simulate travis
# Usage:
#   simulate.sh [MATRIX] [OPTIONS]
#
#   MATRIX:         test matrix to run
#                   One of javascript, python-catchall, python-group-0, python-sharded
#   OPTIONS:
#       --override-test       [List of Django test labels to run instead of matrix default]
#       --override-command    [Override test command completely]
#
# e.g.
#   simulate.sh python-05 --override-test app_manager.SuiteTest
#   simulate.sh python-05 --override-command bash

set -e

TRAVIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR=$( dirname "${TRAVIS_DIR}")

LOCALSETTINGS=$BASE_DIR/localsettings.py
LOCALSETTINGS_TMP=$BASE_DIR/localsettings.tmp.py

set_env() {
    export MATRIX_TYPE=$1
    export NOSE_DIVIDED_WE_RUN=$2
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

OPTIONS="javascript|python-05|python-6a|python-bf|python-sharded"

MATRIX="$1"
shift

while [[ $# > 1 ]]
    do
    opt="$1"

    case $opt in
        --override-test)
            export TEST_OVERRIDE="$2"
            shift
            ;;
        --override-command)
            export COMMAND_OVERRIDE="$2"
            shift
            ;;
        *)
            echo "Unknown option: $opt"
        ;;
    esac
    shift
done

case $MATRIX in
    -h | --help | help)
        echo "simulate.sh [$OPTIONS]"
        exit
        ;;
    javascript)
        set_env javascript "" yes yes
        ;;
    python-05)
        set_env python "05" yes yes
        ;;
    python-6a)
        set_env python "6a" yes yes
        ;;
    python-bf)
        set_env python "bf" yes yes
        ;;
    python-sharded)
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
