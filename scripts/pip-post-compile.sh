#!/usr/bin/env bash
set -e

scripts/pip-post-compile-edx.sh "$@"

function clean_file {
    FILE_PATH=$1
    TEMP_FILE=${FILE_PATH}.tmp
    grep -v '^appnope==' ${FILE_PATH} > ${TEMP_FILE}
    mv ${TEMP_FILE} ${FILE_PATH}
}

for i in "$@"; do
    case ${i} in
        -h|--help)
            exit 0
            ;;
        *)
            clean_file ${i}
            ;;
    esac
done
