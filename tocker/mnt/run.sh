#! /bin/bash
set -e

if [ -z "$1" ]; then
    # the main container need not stay running for services
    exit 0
fi

function test_setup() {
    [ -n "$1" ] && TEST="$1"

    if [ "$TEST" = "python" -o "$TEST" = "python-sharded" ]; then

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
        bower install
    fi

    /mnt/wait.sh
}

function run_tests() {
    TEST="$1"
    if [ "$TEST" != "javascript" -a "$TEST" != "python" -a "$TEST" != "python-sharded" ]; then
        echo "Unknown test suite: $TEST"
        exit 1
    fi
    shift
    test_setup $TEST

    ln -sf .travis/localsettings.py localsettings.py
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
        echo "./manage.py test $@ $TESTS"
        ./manage.py test "$@" $TESTS
    else
        ./manage.py migrate --noinput
        grunt mocha "$@"
    fi
}

# commcare-hq source overlay prevents modifications in this container
# from leaking to the host; allows safe overwrite of localsettings.py
rm -rf /mnt/lib/overlay  # clear source overlay
mkdir -p commcare-hq lib/overlay
mount -t aufs -o br=lib/overlay:commcare-hq-ro none /mnt/commcare-hq

cd commcare-hq

"$@"
