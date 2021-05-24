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


function logmsg {
    local echo_args=( -e )
    local script=$(basename "$0")
    local levelname="$1"
    shift
    if [ "x${1}" == "x-n" ]; then
        shift
        echo_args+=( -n )
    fi
    local msg="$*"
    local ccode=''
    local reset=''
    if [ -t 2 ]; then
        # only define color codes when STDERR is a tty
        local color='0' # default no color
        case "$levelname" in
            DEBUG)
                color='1;35' # magenta
                ;;
            INFO)
                color='1;32' # green
                ;;
            WARNING)
                color='0;33' # gold
                ;;
            ERROR)
                color='1;31' # red
                ;;
        esac
        ccode="\\033[${color}m"
        reset='\033[0m'
    fi
    echo "${echo_args[@]}" "[${script}] ${ccode}${levelname}${reset}: $msg" >&2
}

function func_text {
    local func_name
    for func_name in "$@"; do
        if ! type "$func_name" 2>&1 | grep -E " is a function$" >/dev/null; then
            logmsg ERROR "$func_name is not a function"
            return 1
        fi
        type "$func_name" | tail -n +2
        echo ''
    done
}

function truthy {
    function _usage {
        logmsg ERROR "USAGE: truthy [false|true|no|yes|off|on|0|1]"
        logmsg ERROR "$*"
    }
    if [ $# -gt 1 ]; then
        _usage "too many arguments: $*"
        exit 1
    fi
    local value="$1"
    if [ -n "$value" ]; then
        if echo "$value" | grep -Ei '^(t(rue)?|y(es)?|on|1)$' >/dev/null; then
            return 0
        elif echo "$value" | grep -Ei '^(f(alse)?|n(o)?|off|0)$' >/dev/null; then
            return 1
        else
            _usage "invalid boolean string: '$value'"
            exit 1
        fi
    else
        # absent == false
        return 1
    fi
}

function setup {
    [ -n "$1" ] && TEST="$1"
    logmsg INFO "performing setup..."

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

function run_tests {
    TEST="$1"
    if [ "$TEST" != "javascript" -a "$TEST" != "python" -a "$TEST" != "python-sharded" -a "$TEST" != "python-sharded-and-javascript" ]; then
        logmsg ERROR "Unknown test suite: $TEST"
        exit 1
    fi
    shift
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
            logdo cat -n ../run_tests
        }
        echo -e "$(func_text overlay_debug)\\noverlay_debug" | su cchq -c "/bin/bash -" || true
    else
        # ensure overlayfs (CWD) is readable and emit a useful message if it is not
        if ! su cchq -c "test -r ."; then
            logmsg ERROR "commcare-hq filesystem (${DOCKER_HQ_OVERLAY}) is not readable (consider setting/changing DOCKER_HQ_OVERLAY)"
            exit 1
        fi

        now=$(date +%s)
        setup "$TEST"
        delta=$(($(date +%s) - $now))

        send_timing_metric_to_datadog "setup" $delta

        now=$(date +%s)
        argv_str=$(printf ' %q' "$TEST" "$@")
        su cchq -c "/bin/bash ../run_tests $argv_str"
        [ "$TEST" == "python-sharded-and-javascript" ] && scripts/test-make-requirements.sh
        [ "$TEST" == "python-sharded-and-javascript" -o "$TEST_MIGRATIONS" ] && scripts/test-django-migrations.sh
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
    if [ "$TEST" == "python-sharded" -o "$TEST" == "python-sharded-and-javascript" ]; then
        export USE_PARTITIONED_DATABASE=yes
        # TODO make it possible to run a subset of python-sharded tests
        TESTS="--attr=sql_backend"
    else
        TESTS=""
    fi

    if [ "$TEST" == "python-sharded-and-javascript" ]; then
        ./manage.py create_kafka_topics
        logmsg INFO "./manage.py test $* $TESTS"
        ./manage.py test "$@" $TESTS

        ./manage.py migrate --noinput
        ./manage.py runserver 0.0.0.0:8000 &> commcare-hq.log &
        /mnt/wait.sh 127.0.0.1:8000
        logmsg INFO "grunt test $*"
        grunt test "$@"

        if [ "$TRAVIS_EVENT_TYPE" == "cron" ]; then
            echo "----------> Begin Static Analysis <----------"
            COMMCAREHQ_BOOTSTRAP="yes" ./manage.py static_analysis --datadog
            ./scripts/static-analysis.sh datadog
            echo "----------> End Static Analysis <----------"
        fi

    elif [ "$TEST" != "javascript" ]; then
        ./manage.py create_kafka_topics
        logmsg INFO "./manage.py test $* $TESTS"
        ./manage.py test "$@" $TESTS
    else
        ./manage.py migrate --noinput
        ./manage.py runserver 0.0.0.0:8000 &> commcare-hq.log &
        host=127.0.0.1 /mnt/wait.sh hq:8000
        logmsg INFO "grunt test $*"
        grunt test "$@"
    fi
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
            logmsg INFO -n "chmod'ing commcare-hq overlay... "
            now=$(date +%s)
            # add world-read (and world-x for dirs and existing-x files)
            chmod -R o+rX commcare-hq
            delta=$(($(date +%s) - $now))
            echo "(delta=${delta}sec)" >&2  # append the previous log line
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
    # Replace the existing symlink (links to RO mount, cchq may not have read/x)
    # with one that points at the overlay mount.
    ln -sf commcare-hq/docker/wait.sh wait.sh
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

mkdir -p lib/sharedfiles
ln -sf /mnt/lib/sharedfiles /sharedfiles
chown cchq:cchq lib/sharedfiles

cd commcare-hq
ln -sf docker/localsettings.py localsettings.py

logmsg INFO "running: $*"
"$@"
