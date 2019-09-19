#!/usr/bin/env bash
set -e

scripts/pip-post-compile-edx.sh "$@"

function clean_file {
    FILE_PATH=$1
    TEMP_FILE=${FILE_PATH}.tmp
    grep -v '^appnope==' ${FILE_PATH} > ${TEMP_FILE}
    mv ${TEMP_FILE} ${FILE_PATH}
    grep -v '^eventlet==.*\# via errand-boy$' ${FILE_PATH} > ${TEMP_FILE}
    mv ${TEMP_FILE} ${FILE_PATH}
    grep -v '# via eventlet$' ${FILE_PATH} > ${TEMP_FILE}
    mv ${TEMP_FILE} ${FILE_PATH}
    grep '^eventlet==' ${FILE_PATH} && {
        echo "The dependency chain contains eventlet, a library that clashes with gevent:"
        echo "https://github.com/gevent/gevent/issues/577."
        echo "Specifically, we have had problems with this on the sms_queue celery processor."
        exit -1
    } || :;
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
