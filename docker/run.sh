#! /bin/bash
# This script runs inside the web container
set -e

if [ -z "$1" ]; then
    # the main container need not stay running for services
    exit 0
fi

function setup() {
    [ -n "$1" ] && TEST="$1"

    rm *.log || true

    pip-sync requirements/test-requirements.txt
    pip check  # make sure there are no incompatibilities in test-requirements.txt

    # compile pyc files
    python -m compileall -q corehq custom submodules testapps *.py

    if [[ "$TEST" =~ ^python ]]; then
        keytool -genkey \
            -keyalg RSA \
            -keysize 2048 \
            -validity 10000 \
            -alias javarosakey \
            -keypass onetwothreefourfive \
            -keystore InsecureTestingKeyStore \
            -storepass onetwothreefourfive \
            -dname 'CN=Foo, OU=Bar, O=Bizzle, L=Bazzle, ST=Bingle, C=US'
    fi

    if [ "$TEST" = "javascript" -o "$JS_SETUP" = "yes" ]; then
        yarn install --progress=false --frozen-lockfile
    fi

    /mnt/wait.sh
}

function run_tests() {
    TEST="$1"
    if [ "$TEST" != "javascript" -a "$TEST" != "python" -a "$TEST" != "python-sharded" -a "$TEST" != "python-sharded-and-javascript"]; then
        echo "Unknown test suite: $TEST"
        exit 1
    fi
    shift

    now=`date +%s`
    setup $TEST
    delta=$((`date +%s` - $now))

    send_timing_metric_to_datadog "setup" $delta

    now=`date +%s`
    su cchq -c "../run_tests $TEST $(printf " %q" "$@")"
    [ "$TEST" == "python-sharded-and-javascript" ] && scripts/test-make-requirements.sh
    [ "$TEST" == "python-sharded-and-javascript" -o "$TEST_MIGRATIONS" ] && scripts/test-django-migrations.sh
    delta=$((`date +%s` - $now))

    send_timing_metric_to_datadog "tests" $delta
    send_counter_metric_to_datadog
}

function send_timing_metric_to_datadog() {
    send_metric_to_datadog "travis.timings.$1" $2 "gauge" "test_type:$TEST"
}

function send_counter_metric_to_datadog() {
    send_metric_to_datadog "travis.count" 1 "counter" "test_type:$TEST"
}

function _run_tests() {
    TEST=$1
    shift
    if [ "$TEST" == "python-sharded" -o "$TEST" == "python-sharded-and-javascript" ]; then
        export USE_PARTITIONED_DATABASE=yes
        # TODO make it possible to run a subset of python-sharded tests
        TESTS="--attr=sql_backend"
    else
        TESTS=""
    fi

    if [ "$TEST" == "python-sharded-and-javascript" ]; then
        ./manage.py create_kafka_topics
        echo "./manage.py test $@ $TESTS"
        ./manage.py test "$@" $TESTS

        ./manage.py migrate --noinput
        ./manage.py runserver 0.0.0.0:8000 &> commcare-hq.log &
        /mnt/wait.sh 127.0.0.1:8000
         echo "grunt test $@"
         grunt test "$@"

         if [ "$TRAVIS_EVENT_TYPE" == "cron" ]; then
            echo "----------> Begin Static Analysis <----------"
            COMMCAREHQ_BOOTSTRAP="yes" ./manage.py static_analysis --datadog
            ./scripts/static-analysis.sh datadog
            echo "----------> End Static Analysis <----------"
         fi

    elif [ "$TEST" != "javascript" ]; then
        ./manage.py create_kafka_topics
        echo "./manage.py test $@ $TESTS"
        ./manage.py test "$@" $TESTS
    else
        ./manage.py migrate --noinput
        ./manage.py runserver 0.0.0.0:8000 &> commcare-hq.log &
        host=127.0.0.1 /mnt/wait.sh hq:8000
         echo "grunt test $@"
         grunt test "$@"
    fi
}

function bootstrap() {
    JS_SETUP=yes setup python
    su cchq -c "export CCHQ_IS_FRESH_INSTALL=1 &&
                ./manage.py sync_couch_views &&
                ./manage.py migrate --noinput &&
                ./manage.py compilejsi18n &&
                ./manage.py create_kafka_topics &&
                ./manage.py make_superuser admin@example.com"
}

function runserver() {
    JS_SETUP=yes setup python
    su cchq -c "./manage.py runserver $@ 0.0.0.0:8000"
}

source /mnt/commcare-hq-ro/scripts/datadog-utils.sh  # provides send_metric_to_datadog

export -f setup
export -f run_tests
export -f bootstrap

# put _run_tests body code in a file so it can be run as cchq
printf "#! /bin/bash\nset -e\n" > /mnt/run_tests
type _run_tests | tail -n +4 | head -n -1 >> /mnt/run_tests
chmod +x /mnt/run_tests

cd /mnt
if [ "$DOCKER_HQ_OVERLAY" == "none" ]; then
    ln -s commcare-hq-ro commcare-hq
    mkdir commcare-hq/staticfiles
    chown cchq:cchq commcare-hq-ro commcare-hq/staticfiles
else
    # commcare-hq source overlay prevents modifications in this container
    # from leaking to the host; allows safe overwrite of localsettings.py
    rm -rf lib/overlay  # clear source overlay
    mkdir -p commcare-hq lib/overlay lib/node_modules lib/staticfiles
    ln -s /mnt/lib/node_modules lib/overlay/node_modules
    ln -s /mnt/lib/staticfiles lib/overlay/staticfiles
    if [ "$DOCKER_HQ_OVERLAY" == "overlayfs" ]; then
        rm -rf lib/work
        mkdir lib/work
        mount -t overlay -olowerdir=commcare-hq-ro,upperdir=lib/overlay,workdir=lib/work overlay commcare-hq
    else
        mount -t aufs -o br=lib/overlay:commcare-hq-ro none commcare-hq
    fi
    chown cchq:cchq lib/overlay lib/staticfiles
fi

mkdir -p lib/sharedfiles
ln -sf /mnt/lib/sharedfiles /sharedfiles
chown cchq:cchq lib/sharedfiles

cd commcare-hq
ln -sf docker/localsettings.py localsettings.py

echo "running: $@"
"$@"
