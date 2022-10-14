#! /bin/bash
# This script runs inside the web container
set -e

if [ -z "$1" ]; then
    # the main container need not stay running for services
    exit 0
fi


# NOTE: the following variable is:
#   - Used by the 'run_tests' subcommand only.
#   - Not externally exposed because it's only useful for debugging this script.
# Enabling this option skips setup and actual tests and instead runs some recon
# commands inside the container for debugging overlay filesystem configurations,
# owners and file modes.
DOCKER_OVERLAY_TEST_DEBUG='no'

VALID_TEST_SUITES=(
    javascript
    python
    python-sharded
    python-sharded-and-javascript
    python-elasticsearch-v5
)


function setup {
    [ -n "$1" ] && TEST="$1"
    logmsg INFO "performing setup..."

    rm *.log || true

    pip-sync requirements/test-requirements.txt
    pip check  # make sure there are no incompatibilities in test-requirements.txt
    python_preheat  # preheat the python libs

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

function python_preheat {
    # Perform preflight operations as the container's root user to "preheat"
    # libraries used by Django.
    #
    # Import the `eulxml.xmlmap` module which checks if its lextab module
    # (.../eulxml/xpath/lextab.py) is up-to-date and writes a new lextab.py file
    # if not. This write fails if performed by the container's cchq user due to
    # insufficient filesystem permissions at that path. E.g.
    #   WARNING: Couldn't write lextab module 'eulxml.xpath.lextab'. [Errno 13] Permission denied: '/vendor/lib/python3.6/site-packages/eulxml/xpath/lextab.py'
    #
    # NOTE: This "preheat" can also be performed by executing a no-op manage
    # action (e.g. `manage.py test -h`), but this operation is heavy-handed and
    # importing the python module directly is done instead to improve
    # performance.
    logmsg INFO "preheating python libraries"
    # send to /dev/null and allow to fail
    python -c 'import eulxml.xmlmap' >/dev/null 2>&1 || true
}

function run_tests {
    # Disabled due to: https://github.com/github/feedback/discussions/8848
    # [ -n "$GITHUB_ACTIONS" ] && echo "::endgroup::"  # "Docker setup" begins in scripts/docker
    TEST="$1"
    shift
    suite_pat=$(printf '%s|' "${VALID_TEST_SUITES[@]}" | sed -E 's/\|$//')
    if ! echo "$TEST" | grep -E "^(${suite_pat})$" >/dev/null; then
        logmsg ERROR "invalid test suite: $TEST (choices=${suite_pat})"
        exit 1
    fi
    if truthy "$DOCKER_OVERLAY_TEST_DEBUG"; then
        # skip setup and tests and run debugging commands instead
        function overlay_debug {
            function logdo {
                echo -e "\\n$ $*"
                "$@"
            }
            logdo sh -c "mount | grep 'on /mnt/'"
            logdo id
            logdo pwd
            logdo ls -ld . .. corehq manage.py node_modules staticfiles docker/wait.sh
            if logdo df -hP .; then
                upone=..
            else
                # can't read CWD, use absolute path
                upone=$(dirname "$(pwd)")
            fi
            logdo ls -la "$upone"
            for dirpath in $(find /mnt -mindepth 1 -maxdepth 1 -type d -not -name 'commcare-hq*'); do
                logdo ls -la "$dirpath"
            done
            logdo python -m site
            logdo pip freeze
            logdo npm config list
            logdo yarn --version
            logdo cat -n ../run_tests
        }
        echo -e "$(func_text overlay_debug)\\noverlay_debug" | su cchq -c "/bin/bash -" || true
    else
        # ensure overlayfs (CWD) is readable and emit a useful message if it is not
        if ! su cchq -c "test -r ."; then
            logmsg ERROR "commcare-hq filesystem (${DOCKER_HQ_OVERLAY}) is not readable (consider setting/changing DOCKER_HQ_OVERLAY)"
            exit 1
        fi

        log_group_begin "Django test suite setup"
        now=$(date +%s)
        setup "$TEST"
        delta=$(($(date +%s) - $now))
        log_group_end

        send_timing_metric_to_datadog "setup" $delta

        log_group_begin "Django test suite: $TEST"
        now=$(date +%s)
        argv_str=$(printf ' %q' "$TEST" "$@")
        su cchq -c "/bin/bash ../run_tests $argv_str" 2>&1
        log_group_end  # only log group end on success (notice: `set -e`)
        [ "$TEST" == "python-sharded-and-javascript" ] && scripts/test-prod-entrypoints.sh
        [ "$TEST" == "python-sharded-and-javascript" ] && scripts/test-make-requirements.sh
        [ "$TEST" == "python-sharded-and-javascript" ] && scripts/test-serializer-pickle-files.sh
        [ "$TEST" == "python-sharded-and-javascript" -o "$TEST_MIGRATIONS" ] && scripts/test-django-migrations.sh
        [ "$TEST" == "python-sharded-and-javascript" ] && scripts/track-dependency-status.sh
        delta=$(($(date +%s) - $now))

        send_timing_metric_to_datadog "tests" $delta
        send_counter_metric_to_datadog
    fi
}

function send_timing_metric_to_datadog() {
    send_metric_to_datadog "travis.timings.$1" $2 "gauge" "test_type:$TEST"
}

function send_counter_metric_to_datadog() {
    send_metric_to_datadog "travis.count" 1 "counter" "test_type:$TEST"
}

function _run_tests {
    # NOTE: this function is only used as source code which gets written to a
    # file and executed by the test runner. It does not have implicit access to
    # the defining-script's environment (variables, functions, etc). Do not use
    # resources defined elsewhere in this *file* within this function unless
    # they also get written into the destination script.
    set -e
    TEST="$1"
    shift
    py_test_args=("$@")
    js_test_args=("$@")
    case "$TEST" in
        python-sharded*)
            export USE_PARTITIONED_DATABASE=yes
            # TODO make it possible to run a subset of python-sharded tests
            py_test_args+=("--attr=sharded")
            ;;
        python-elasticsearch-v5)
            export ELASTICSEARCH_HOST='elasticsearch5'
            export ELASTICSEARCH_PORT=9205
            export ELASTICSEARCH_MAJOR_VERSION=5
            py_test_args+=("--attr=es_test")
            ;;
    esac

    function _test_python {
        ./manage.py create_kafka_topics
        if [ -n "$CI" ]; then
            logmsg INFO "coverage run manage.py test ${py_test_args[*]}"
            # `coverage` generates a file that's then sent to codecov
            coverage run manage.py test "${py_test_args[@]}"
            coverage xml
            if [ -n "$TRAVIS" ]; then
                bash <(curl -s https://codecov.io/bash)
            fi
        else
            logmsg INFO "./manage.py test ${py_test_args[*]}"
            ./manage.py test "${py_test_args[@]}"
        fi
    }

    function _test_javascript {
        ./manage.py migrate --noinput
        ./manage.py runserver 0.0.0.0:8000 &> commcare-hq.log &
        /mnt/wait.sh 127.0.0.1:8000
        logmsg INFO "grunt test ${js_test_args[*]}"
        grunt test "${js_test_args[@]}"
    }

    case "$TEST" in
        python-sharded-and-javascript)
            _test_python
            _test_javascript
            ./manage.py static_analysis
            ;;
        python|python-sharded|python-elasticsearch-v5)
            _test_python
            ;;
        javascript)
            _test_javascript
            ;;
        *)
            # this should never happen (would mean there is a bug in this script)
            logmsg ERROR "invalid TEST value: '${TEST}'"
            exit 1
            ;;
    esac
}

function bootstrap {
    JS_SETUP=yes setup python
    su cchq -c "export CCHQ_IS_FRESH_INSTALL=1 &&
                ./manage.py sync_couch_views &&
                ./manage.py migrate --noinput &&
                ./manage.py compilejsi18n &&
                ./manage.py create_kafka_topics &&
                ./manage.py make_superuser admin@example.com"
}

function runserver {
    JS_SETUP=yes setup python
    su cchq -c "./manage.py runserver $@ 0.0.0.0:8000"
}

function runcelery {
    JS_SETUP=yes setup python
    su cchq -c "celery -A corehq worker -l info"
}

function runpillowtop {
    setup python
    su cchq -c "./manage.py run_ptop --all --processor-chunk-size=1"
}

source /vendor/scripts/datadog-utils.sh  # provides send_metric_to_datadog
source /vendor/scripts/bash-utils.sh  # provides logmsg, log_group_{begin,end}, func_text and truthy

# build the run_tests script to be executed as cchq later
func_text logmsg _run_tests  > /mnt/run_tests
echo '_run_tests "$@"'      >> /mnt/run_tests

cd /mnt
if ! [[ -h commcare-hq ]]
then
    ln -s /vendor commcare-hq
    mkdir commcare-hq/staticfiles
    chown cchq:cchq /vendor commcare-hq/staticfiles
fi

mkdir -p lib/sharedfiles
ln -sf /mnt/lib/sharedfiles /sharedfiles
chown cchq:cchq lib/sharedfiles

cd commcare-hq
ln -sf docker/localsettings.py localsettings.py

logmsg INFO "running: $*"
"$@"
