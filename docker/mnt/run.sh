#! /bin/bash
set -e

if [ -z "$1" ]; then
    # the main container need not stay running for services
    exit 0
fi

function setup() {
    [ -n "$1" ] && TEST="$1"

    if [[ "$TEST" =~ ^python ]]; then

        scripts/uninstall-requirements.sh
        pip install \
            -r requirements/requirements.txt \
            -r requirements/dev-requirements.txt \
            coveralls

        # some kind of optimization?
        # skip Running setup.py bdist_wheel for ... ?
        rm -rf /root/.cache/pip

        /usr/lib/jvm/jdk1.7.0/bin/keytool -genkey \
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
        npm install
        bower install --config.interactive=false
    fi

    /mnt/wait.sh

    if [[ "$TEST" =~ ^python ]]; then
        su cchq -c "./manage.py create_kafka_topics"
    fi
}

function run_tests() {
    TEST="$1"
    if [ "$TEST" != "javascript" -a "$TEST" != "python" -a "$TEST" != "python-sharded" ]; then
        echo "Unknown test suite: $TEST"
        exit 1
    fi
    shift
    setup $TEST
    su cchq -c "../run_tests $TEST $(printf " %q" "$@")"
}

function _run_tests() {
    TEST=$1
    shift
    if [ "$TEST" == "python-sharded" ]; then
        export USE_PARTITIONED_DATABASE=yes
        # TODO make it possible to run a subset of python-sharded tests
        TESTS=" \
            corehq.form_processor \
            corehq.sql_db \
            couchforms \
            casexml.apps.case \
            casexml.apps.phone \
            corehq.apps.receiverwrapper"
    else
        TESTS=""
    fi

    if [ "$TEST" != "javascript" ]; then
        echo "coverage run manage.py test $@ $TESTS"
        /vendor/bin/coverage run manage.py test "$@" $TESTS
    else
        ./manage.py migrate --noinput
        ./manage.py runserver 0.0.0.0:8000 &> /var/log/commcare-hq.log &
        host=127.0.0.1 port=8000 /mnt/wait.sh hq
        # HACK curl to avoid
        # Warning: PhantomJS timed out, possibly due to a missing Mocha run() call.
        curl http://localhost:8000/mocha/app_manager/ &> /dev/null
        echo "grunt mocha $@"
        grunt mocha "$@"
    fi
}

function bootstrap() {
    JS_SETUP=yes setup python
    ./manage.py sync_couch_views
    ./manage.py migrate --noinput
    ./manage.py compilejsi18n
    ./manage.py bootstrap demo admin@example.com password
}

export -f setup
export -f run_tests
export -f bootstrap

# put _run_tests body code in a file so it can be run as cchq
printf "#! /bin/bash\nset -e\n" > /mnt/run_tests
type _run_tests | tail -n +4 | head -n -1 >> /mnt/run_tests
chmod +x /mnt/run_tests

cd /mnt
if [ "$TRAVIS" == "true" ]; then
    ln -s commcare-hq-ro commcare-hq
else
    # commcare-hq source overlay prevents modifications in this container
    # from leaking to the host; allows safe overwrite of localsettings.py
    rm -rf lib/overlay  # clear source overlay
    mkdir -p commcare-hq lib/overlay lib/node_modules
    ln -s /mnt/lib/node_modules lib/overlay/node_modules
    mount -t aufs -o br=lib/overlay:commcare-hq-ro none commcare-hq
    chown cchq:cchq lib/overlay
fi

mkdir -p lib/sharedfiles
ln -s /mnt/lib/sharedfiles /sharedfiles
chown cchq:cchq lib/sharedfiles

cd commcare-hq
ln -sf docker/localsettings.py localsettings.py

echo "running: $@"
"$@"
