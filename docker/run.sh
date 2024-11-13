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

    if [ -n "$GITHUB_ACTIONS" ]; then
        # create the artifacts dir with container-write ownership
        install -dm0755 -o cchq -g cchq ./artifacts
    fi

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
            logdo ls -ld . .. corehq manage.py node_modules staticfiles
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
        if [ "$TEST" == "python-sharded-and-javascript" ]; then
            logmsg INFO "Building Webpack"
            chown -R cchq:cchq ./webpack
            su cchq -c "yarn build"
            su cchq -c scripts/test-prod-entrypoints.sh
            scripts/test-make-requirements.sh
            scripts/test-serializer-pickle-files.sh
            su cchq -c scripts/test-django-migrations.sh
        fi
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
            py_test_args+=("-msharded")
            ;;
        python-elasticsearch-v5)
            export ELASTICSEARCH_HOST='elasticsearch5'
            export ELASTICSEARCH_PORT=9205
            export ELASTICSEARCH_MAJOR_VERSION=5
            py_test_args+=("-mes_test")
            ;;
    esac

    function _test_python {
        ./manage.py create_kafka_topics
        if [ -n "$CI" ]; then
            logmsg INFO "coverage run $(which pytest) ${py_test_args[*]}"
            # `coverage` generates a file that's then sent to codecov
            coverage run $(which pytest) "${py_test_args[@]}"
            coverage xml
            if [ -n "$TRAVIS" ]; then
                bash <(curl -s https://codecov.io/bash)
            fi
        else
            logmsg INFO "pytest ${py_test_args[*]}"
            pytest "${py_test_args[@]}"
        fi
    }

    function _wait_for_runserver {
        began=$(date +%s)
        while ! { exec 6<>/dev/tcp/127.0.0.1/8000; } 2>/dev/null; do
            if [ $(($(date +%s) - $began)) -gt 90 ]; then
                logmsg ERROR "timed out (90 sec) waiting for 127.0.0.1:8000"
                exit 1
            fi
            sleep 1
        done
    }

    function _test_javascript {
        SKIP_GEVENT_PATCHING=1 ./manage.py migrate --noinput
        ./manage.py runserver 0.0.0.0:8000 &> commcare-hq.log &
        _wait_for_runserver
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

source /mnt/commcare-hq-ro/scripts/datadog-utils.sh  # provides send_metric_to_datadog
source /mnt/commcare-hq-ro/scripts/bash-utils.sh  # provides logmsg, log_group_{begin,end}, func_text and truthy

# build the run_tests script to be executed as cchq later
func_text logmsg _run_tests  > /mnt/run_tests
echo '_run_tests "$@"'      >> /mnt/run_tests

# Initial state of /mnt docker volumes:
# /mnt/commcare-hq-ro:
#   - points to local commcare-hq repo directory
#   - read-only (except for travis).
# /mnt/lib:
#   - empty (except for travis)
cd /mnt
if [ "$DOCKER_HQ_OVERLAY" == "none" ]; then
    ln -s commcare-hq-ro commcare-hq
    mkdir commcare-hq/staticfiles
    chown cchq:cchq commcare-hq-ro commcare-hq/staticfiles
else
    # commcare-hq source overlay prevents modifications in this container
    # from leaking to the host; allows safe overwrite of localsettings.py
    rm -rf lib/overlay  # clear source overlay (if it exists)
    mkdir -p commcare-hq lib/{overlay,node_modules,staticfiles}
    ln -s /mnt/lib/node_modules lib/overlay/node_modules
    ln -s /mnt/lib/staticfiles lib/overlay/staticfiles
    logmsg INFO "mounting $(pwd)/commcare-hq via $DOCKER_HQ_OVERLAY"
    if [ "$DOCKER_HQ_OVERLAY" == "overlayfs" ]; then
        # Default Docker overlay engine
        rm -rf lib/work
        mkdir lib/work
        overlayopts="lowerdir=/mnt/commcare-hq-ro,upperdir=/mnt/lib/overlay,workdir=/mnt/lib/work"
        if truthy "$DOCKER_HQ_OVERLAYFS_METACOPY"; then
            # see: https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html#metadata-only-copy-up
            # Significantly speeds up recursive chmods (<1sec when enabled
            # compared to ~20sec when not). Provided as a configurable setting
            # since there are security implications.
            overlayopts="metacopy=on,${overlayopts}"
        fi
        mount -t overlay -o"$overlayopts" overlay commcare-hq
        if truthy "$DOCKER_HQ_OVERLAYFS_CHMOD"; then
            # May be required so cchq user can read files in the mounted
            # commcare-hq volume. Provided as a configurable setting because it
            # is an expensive operation and some container ecosystems (travis
            # perhaps?) may not require it. I suspect this is the reason local
            # testing was not working for many people in the past.
            logmsg -n INFO "chmod'ing commcare-hq overlay... "
            now=$(date +%s)
            # add world-read (and world-x for dirs and existing-x files)
            chmod -R o+rX commcare-hq
            delta=$(($(date +%s) - $now))
            echo "(delta=${delta}sec)"  # append the previous log line
        fi
    else
        # This (aufs) was the default (perhaps only?) Docker overlay engine when
        # this script was originally written, and has hung around ever since.
        # Likely because this script has not been kept up-to-date with the
        # latest Docker features.
        #
        # TODO: use overlayfs and drop support for aufs
        mount -t aufs -o br=/mnt/lib/overlay:/mnt/commcare-hq-ro none commcare-hq
    fi
    # Own the new dirs after the overlay is mounted.
    chown cchq:cchq commcare-hq lib/{overlay,node_modules,staticfiles}
fi
# New state of /mnt (depending on value of DOCKER_HQ_OVERLAY):
#
# none (travis, typically):
#   /mnt
#   ├── commcare-hq -> commcare-hq-ro
#   ├── commcare-hq-ro  # NOTE: not read-only
#   │   ├── staticfiles
#   │   │   └── [empty]
#   │   └── [existing commcare-hq files...]
#   └── lib
#       └── [maybe files with travis...]
#
# overlayfs:
#   /mnt
#   ├── commcare-hq
#   │   └── [overlayfs of /mnt/commcare-hq-ro + /mnt/lib/overlay + /mnt/lib/work]
#   ├── commcare-hq-ro
#   │   └── [existing commcare-hq files...]
#   └── lib
#       ├── node_modules
#       ├── overlay
#       │   ├── node_modules -> /mnt/lib/node_modules
#       │   └── staticfiles -> /mnt/lib/staticfiles
#       ├── staticfiles
#       └── work
#
# aufs:
#   /mnt
#   ├── commcare-hq
#   │   └── [aufs of /mnt/commcare-hq-ro + /mnt/lib/overlay]
#   ├── commcare-hq-ro
#   │   └── [existing commcare-hq files...]
#   └── lib
#       ├── node_modules
#       ├── overlay
#       │   ├── node_modules -> /mnt/lib/node_modules
#       │   └── staticfiles -> /mnt/lib/staticfiles
#       └── staticfiles

mkdir -p lib/sharedfiles /home/cchq
ln -sf /mnt/lib/sharedfiles /sharedfiles
chown cchq:cchq lib/sharedfiles /home/cchq
su cchq -c "/usr/bin/git config --global --add safe.directory /mnt/commcare-hq-ro"
/usr/bin/git config --global --add safe.directory /mnt/commcare-hq-ro

cd commcare-hq
ln -sf docker/localsettings.py localsettings.py

logmsg INFO "running: $*"
"$@"
