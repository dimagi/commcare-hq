#!/usr/bin/env bash
# This is a hack so that we can run moto_server prior to running the tests.
# This should be possible by using a command like `bash -c "moto_server && ./manage.py test"
# but there seems to be a bug in docker-compose that prevents the second command from
# running.
#
# It should also be possible to run moto-server in a separate container but when doing that
# all the S3 requests failed with `bucket does not exist` errors.
#

set -e

TESTS="$1"
COMMAND="coverage run manage.py test --noinput --failfast --traceback --verbosity=2"

/moto-s3/env/bin/moto_server s3 &

if [ -z ${COMMAND_OVERRIDE} ]; then
    $COMMAND $TESTS
else
    $COMMAND_OVERRIDE
fi
