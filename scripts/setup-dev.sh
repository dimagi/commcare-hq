#!/usr/bin/env bash
#
# Set up a CommCare HQ development environment on macOS.
#
# Every step checks its own precondition before acting, so this is safe to
# re-run: finished work is reported and skipped. That is also what makes
# `--check` able to report an environment's state without changing it.
#
# Anything that installs or downloads is collected into a single plan and
# approved with one prompt, rather than asking repeatedly part way through.
#
# A step that fails does not stop the run. The script does as much as it can and
# summarises what failed at the end, because a half-built environment plus an
# accurate list of what is missing beats stopping at the first problem.
#
# This automates DEV_SETUP.md and DEV_SETUP_MAC.md. Those remain the reference;
# this is a convenience, not a replacement.
#
# Deliberately does not modify your shell profile. Where something needs to be
# on PATH permanently, the script says so and adds it to its own PATH for the
# current run only. That is also why sdkman is reported but never installed here:
# its installer adds itself to your profile, so you run that one yourself.

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

# --- configuration -----------------------------------------------------------

# Minimum front-end tool versions, per DEV_SETUP.md
NODE_MIN_MAJOR=24
NPM_MIN_MAJOR=11

# sdkman is how HQ development manages the JDK that formplayer needs.
JAVA_MAJOR=17
JAVA_SDKMAN_CANDIDATE=17.0.20-zulu
SDKMAN_INIT="$HOME/.sdkman/bin/sdkman-init.sh"
SDKMAN_JAVA_BIN="$HOME/.sdkman/candidates/java/current/bin"
SDKMAN_INSTALL='curl -s "https://get.sdkman.io" | zsh -o NO_NOMATCH'

# formplayer is absent on purpose: its image does not run on macOS, so formplayer
# runs from a jar instead.
SERVICES="postgres couch redis elasticsearch6 zookeeper kafka minio"

VENV_PY="$REPO_ROOT/.venv/bin/python"
TMP_BASE="${TMPDIR:-/tmp}"
# Created per run by mktemp once we know we are acting. A fixed name here would be
# predictable in a world-writable /tmp when TMPDIR is unset (as it is under
# `sudo -i`), where a symlink planted at that path would redirect this run's
# output into whatever it points at.
LOG_FILE=''

FORMPLAYER_JAR_URL=https://s3.amazonaws.com/dimagi-formplayer-jars/latest-successful/formplayer.jar
FORMPLAYER_PROPS_URL=https://raw.githubusercontent.com/dimagi/formplayer/master/config/application.example.properties

# --- options -----------------------------------------------------------------

CHECK_ONLY=false
ASSUME_YES=false

usage() {
    cat <<'EOF'
Set up a CommCare HQ development environment on macOS.

Usage: scripts/setup-dev.sh [options]

  --check      Report what is missing or misconfigured, change nothing.
               Exits non-zero if anything needs attention.
  --yes, -y    Approve the install plan without prompting.
  --help, -h   Show this message.

Safe to re-run: each step checks its precondition and skips finished work.
Anything that installs or downloads is approved with a single prompt, and a
failing step is reported rather than ending the run.

Automates DEV_SETUP.md and DEV_SETUP_MAC.md, which remain the reference.
EOF
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK_ONLY=true ;;
        --yes|-y) ASSUME_YES=true ;;
        --help|-h) usage ;;
        *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
    shift
done

# --- output ------------------------------------------------------------------

if [ -t 1 ] && [ "${TERM:-}" != "dumb" ]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
    RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'
    CLEAR=$'\r\033[K'
else
    BOLD=''; DIM=''; RESET=''
    RED=''; GREEN=''; YELLOW=''; CYAN=''
    CLEAR=''
fi
ESC=$(printf '\033')
TAB=$(printf '\t')

heading() { printf '\n  %s%s%s\n' "$BOLD" "$1" "$RESET"; }
ok()      { printf '  %s✓%s %-22s %s\n' "$GREEN" "$RESET" "$1" "${2:-}"; }
skip()    { printf '  %s·%s %-22s %s%s%s\n' "$DIM" "$RESET" "$1" "$DIM" "${2:-already done}" "$RESET"; }
warn()    { printf '  %s!%s %-22s %s\n' "$YELLOW" "$RESET" "$1" "${2:-}"; }
bad()     { printf '  %s✗%s %-22s %s\n' "$RED" "$RESET" "$1" "${2:-}"; }
info()    { printf '    %s%s%s\n' "$DIM" "$1" "$RESET"; }

have() { command -v "$1" >/dev/null 2>&1; }
acting() { ! $CHECK_ONLY; }
strip_color() { sed "s/${ESC}\[[0-9;]*m//g"; }

# --- state -------------------------------------------------------------------

# PLAN holds actions that install or download, as "label<TAB>shell command".
# They are approved together and run before anything that might depend on them.
PLAN=''
# PENDING/HINTS: things this script will not do, and how to do them by hand.
PENDING=''
HINTS=''
# FAILED: steps that were attempted and did not work.
FAILED=''

plan_add()    { PLAN="${PLAN}${1}${TAB}${2}"$'\n'; }
plan_count()  { printf '%s' "$PLAN" | grep -c . || true; }
pending()     { PENDING="${PENDING}${1}"$'\n'; HINTS="${HINTS}  ${1}: ${2}"$'\n'; }
fail_add()    { FAILED="${FAILED}  ${1}"$'\n'; }
count_lines() { printf '%s' "$1" | grep -c . || true; }

# --- running commands --------------------------------------------------------

SPINNER='⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏'

elapsed() {
    local s=$((SECONDS - $1))
    if [ "$s" -ge 60 ]; then printf '%dm%02ds' $((s / 60)) $((s % 60))
    else printf '%ds' "$s"; fi
}

# Run a command, sending verbose output to the log. Never aborts the script: a
# failure is reported, recorded, and execution continues with the next step.
# Always returns 0 so callers are safe under `set -e`; use `step_ok` to test.
STEP_OK=true
run() {
    local label="$1"; shift
    local start=$SECONDS
    STEP_OK=true

    if [ -z "$CLEAR" ]; then
        if "$@" >>"$LOG_FILE" 2>&1; then
            ok "$label" "done in $(elapsed "$start")"
        else
            STEP_OK=false
        fi
    else
        "$@" >>"$LOG_FILE" 2>&1 &
        local pid=$! i=0
        set -- $SPINNER
        local frames=$# frame
        while kill -0 "$pid" 2>/dev/null; do
            eval "frame=\${$(( i % frames + 1 ))}"
            printf '%s  %s%s%s %-22s %s%s%s' "$CLEAR" "$CYAN" "$frame" "$RESET" \
                "$label" "$DIM" "$(elapsed "$start")" "$RESET"
            i=$((i + 1))
            sleep 0.1
        done
        if wait "$pid"; then
            printf '%s' "$CLEAR"
            ok "$label" "done in $(elapsed "$start")"
        else
            printf '%s' "$CLEAR"
            STEP_OK=false
        fi
    fi

    if ! $STEP_OK; then
        bad "$label" "failed after $(elapsed "$start")"
        info "see $LOG_FILE"
        fail_add "$label"
    fi
    return 0
}

step_ok() { $STEP_OK; }

# do_step LABEL HINT CMD... -- act, or record the hint in --check mode.
do_step() {
    local label="$1" hint="$2"; shift 2
    if acting; then run "$label" "$@"; else pending "$label" "$hint"; fi
}

# --- platform guard ----------------------------------------------------------

if [ "$(uname -s)" != Darwin ]; then
    printf '\n  %sError:%s this script only supports macOS. For Linux, follow DEV_SETUP.md.\n\n' \
        "$RED" "$RESET" >&2
    exit 1
fi

# Only a real run gets a log, and it gets a fresh one. --check writes nothing at
# all, so inspecting an environment cannot destroy the evidence from the run you
# are trying to diagnose.
if acting; then
    LOG_FILE=$(mktemp "${TMP_BASE%/}/hq-setup-dev.XXXXXX")
fi

printf '\n  %sCommCare HQ dev setup%s  %s· macOS %s · %s%s\n' \
    "$BOLD" "$RESET" "$DIM" "$(sw_vers -productVersion)" "$(uname -m)" "$RESET"
$CHECK_ONLY && printf '  %schecking only, nothing will be changed%s\n' "$DIM" "$RESET"
[ -n "$LOG_FILE" ] && printf '  %slog: %s%s\n' "$DIM" "$LOG_FILE" "$RESET"

# --- inspect: prerequisites --------------------------------------------------

heading Prerequisites

if have brew; then
    ok homebrew "$(brew --version | head -1 | awk '{print $2}')"
else
    bad homebrew 'not found'
    pending homebrew 'install from https://brew.sh, then re-run'
fi

# want LABEL FORMULA -- plan a Homebrew install, or explain why it cannot happen.
want_brew() {
    if have brew; then plan_add "$1" "brew install $2"
    else pending "$1" "brew install $2"; fi
}

if have uv; then
    ok uv "$(uv --version | awk '{print $2}')"
else
    bad uv 'not found'
    want_brew uv uv
fi

if have node && have npm; then
    node_v=$(node -v | sed 's/^v//' || true)
    npm_v=$(npm -v)
    if [ "$(printf '%s\n%s\n' "$NODE_MIN_MAJOR" "${node_v%%.*}" | sort -V | head -1)" = "$NODE_MIN_MAJOR" ] \
       && [ "$(printf '%s\n%s\n' "$NPM_MIN_MAJOR" "${npm_v%%.*}" | sort -V | head -1)" = "$NPM_MIN_MAJOR" ]; then
        ok 'node / npm' "v$node_v / $npm_v"
    else
        warn 'node / npm' "v$node_v / $npm_v (want node >= $NODE_MIN_MAJOR, npm >= $NPM_MIN_MAJOR)"
        pending 'node / npm' 'brew upgrade node'
    fi
else
    bad 'node / npm' 'not found'
    want_brew 'node / npm' node
fi

# macOS ships a /usr/bin/java stub that exists but fails with no JDK installed,
# so the version output has to be parsed rather than trusted.
java_major_of() {
    local out
    out=$("$1" -version 2>&1 | head -1) || return 1
    case "$out" in
        *'version "'*) printf '%s' "$out" | sed -E 's/.*version "([0-9]+).*/\1/' ;;
        *) return 1 ;;
    esac
}

# Adds sdkman's JDK to PATH when that is where java lives. Called again after the
# plan runs, since installing it is one of the things the plan can do.
use_sdkman_java() {
    local jm
    [ -x "$SDKMAN_JAVA_BIN/java" ] || return 1
    jm=$(java_major_of "$SDKMAN_JAVA_BIN/java") || return 1
    [ "$jm" = "$JAVA_MAJOR" ] || return 1
    case ":$PATH:" in *":$SDKMAN_JAVA_BIN:"*) ;; *) PATH="$SDKMAN_JAVA_BIN:$PATH"; export PATH ;; esac
    return 0
}

report_java() {
    local jm
    if have java && jm=$(java_major_of java) && [ "$jm" = "$JAVA_MAJOR" ]; then
        ok "java $JAVA_MAJOR" "$(java -version 2>&1 | head -1 | sed -E 's/.*version "([^"]+)".*/\1/')"
        return 0
    fi
    if use_sdkman_java; then
        warn "java $JAVA_MAJOR" 'installed via sdkman but not on PATH'
        info "using $SDKMAN_JAVA_BIN for this run; source sdkman-init.sh in your profile to keep it"
        return 0
    fi
    return 1
}

# sdkman is a prerequisite in its own right, so report it rather than leaving it
# implicit. It is not installed automatically: its installer adds itself to your
# shell profile, and this script does not edit shell profiles.
if [ -s "$SDKMAN_INIT" ]; then
    ok sdkman present
else
    bad sdkman 'not found'
    info 'its installer adds sdkman to your shell profile, which this script will not do'
    info 'run it yourself, then re-run this script to pick up the JDK'
    pending sdkman "$SDKMAN_INSTALL"
fi

if report_java; then
    : # report_java already printed the state
elif [ -s "$SDKMAN_INIT" ]; then
    bad "java $JAVA_MAJOR" 'not installed'
    # sdkman is a set of shell functions, so it has to be sourced first.
    plan_add "java $JAVA_MAJOR" ". \"$SDKMAN_INIT\"; sdk install java $JAVA_SDKMAN_CANDIDATE"
else
    bad "java $JAVA_MAJOR" 'needs sdkman first'
    pending "java $JAVA_MAJOR" "install sdkman, then: sdk install java $JAVA_SDKMAN_CANDIDATE"
fi

if have sass; then
    ok sass "$(sass --version 2>/dev/null | head -1 | awk '{print $1}')"
else
    bad sass 'not found'
    # --ignore-scripts matches the intent of .yarnrc's `ignore-scripts true`: a
    # compromised release should not get to run install hooks as the developer.
    # A repo .npmrc would not cover this, since npm drops project config for -g.
    plan_add sass 'npm install -g --ignore-scripts sass'
fi

if have yarn; then
    ok yarn "$(yarn --version 2>/dev/null)"
else
    bad yarn 'not found'
    want_brew yarn yarn
fi

# Homebrew's postgres formulae are keg-only, so they are frequently installed but
# not on PATH. Re-checked after the plan runs, for the same reason as java.
resolve_pg_keg() {
    local formula p
    have brew || return 1
    for formula in libpq postgresql; do
        if p=$(brew --prefix "$formula" 2>/dev/null) && [ -x "$p/bin/psql" ]; then
            printf '%s' "$p/bin"; return 0
        fi
    done
    return 1
}
# Must not be called from a command substitution: the PATH export would be lost
# in the subshell, leaving psql "found" in the message but absent in practice.
use_pg_keg() {
    local keg
    keg=$(resolve_pg_keg) || return 1
    case ":$PATH:" in *":$keg:"*) ;; *) PATH="$keg:$PATH"; export PATH ;; esac
    PG_KEG="$keg"
    return 0
}

if have psql; then
    ok 'postgres client' "$(psql --version | awk '{print $3}')"
elif use_pg_keg; then
    warn 'postgres client' 'installed but not on PATH (keg-only)'
    info "using $PG_KEG for this run; add it to your shell profile to keep it"
else
    bad 'postgres client' 'not found'
    want_brew 'postgres client' libpq
fi

# --- inspect: container engine -----------------------------------------------

heading 'Container engine'

# Rosetta matters here: two of HQ's images are published only for amd64.
COLIMA_ARGS='--cpu 4 --memory 8 --disk 60'
[ "$(uname -m)" = arm64 ] && COLIMA_ARGS="$COLIMA_ARGS --vm-type vz --vz-rosetta"

if have docker; then
    # `docker version` exits non-zero with no daemon even though it prints the
    # client version, so take the output and ignore the status.
    docker_v=$(docker version --format '{{.Client.Version}}' 2>/dev/null | head -1 || true)
    ok 'docker cli' "${docker_v:-present}"
else
    bad 'docker cli' 'not found'
    want_brew 'docker cli' docker
fi

# The docker CLI is only a client; something has to provide the daemon.
if docker info >/dev/null 2>&1; then
    ok 'docker daemon' reachable
elif have colima; then
    bad 'docker daemon' 'colima installed but not running'
    plan_add 'docker daemon' "colima start $COLIMA_ARGS"
elif have orb; then
    bad 'docker daemon' 'OrbStack installed but not running'
    plan_add 'docker daemon' 'orb start'
elif [ -d /Applications/Docker.app ]; then
    bad 'docker daemon' 'Docker Desktop installed but not running'
    info 'it is a GUI app, so start it yourself rather than from this script'
    pending 'docker daemon' 'open -a Docker'
elif have brew; then
    bad 'docker daemon' 'no container engine installed'
    info 'colima is the lightest option and raises no licensing question'
    info 'DEV_SETUP_MAC.md#container-engines covers Docker Desktop and OrbStack instead'
    plan_add 'container engine' "brew install colima docker-compose && colima start $COLIMA_ARGS"
else
    bad 'docker daemon' 'no container engine installed'
    pending 'docker daemon' 'see DEV_SETUP_MAC.md#container-engines'
fi

# Docker Desktop and OrbStack bundle compose; Homebrew's must be registered.
if docker compose version >/dev/null 2>&1; then
    compose_v=$(docker compose version --short 2>/dev/null | head -1 || true)
    ok 'docker compose' "${compose_v:-present}"
else
    bad 'docker compose' 'not resolving'
    plugin_dir=''
    if have brew && p=$(brew --prefix 2>/dev/null) && [ -d "$p/lib/docker/cli-plugins" ]; then
        plugin_dir="$p/lib/docker/cli-plugins"
    fi
    if [ -n "$plugin_dir" ]; then
        info "plugin is at $plugin_dir but the docker cli is not looking there"
        plan_add 'docker compose' "register_compose_plugin '$plugin_dir'"
    else
        info 'the compose plugin will be installed with the container engine'
    fi
fi

# Merges into ~/.docker/config.json rather than overwriting: that file usually
# holds other keys. Referenced by the plan entry above.
register_compose_plugin() {
    mkdir -p "$HOME/.docker"
    /usr/bin/python3 - "$1" <<'PY'
import json, os, sys
path = os.path.expanduser('~/.docker/config.json')
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        content = f.read().strip()
    cfg = json.loads(content) if content else {}
dirs = cfg.setdefault('cliPluginsExtraDirs', [])
if sys.argv[1] not in dirs:
    dirs.append(sys.argv[1])
# This file holds registry credentials, and docker creates it 0600. Creating it
# at the ambient umask (0644 typically) would leave those readable. An existing
# file keeps whatever mode its owner chose.
os.umask(0o077)
with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')
PY
}

# --- inspect: formplayer files -----------------------------------------------

heading Formplayer

if [ -f formplayer.jar ]; then
    skip formplayer.jar "$(du -h formplayer.jar | awk '{print $1}')"
else
    bad formplayer.jar 'missing (~136MB download)'
    plan_add formplayer.jar "curl -sSL '$FORMPLAYER_JAR_URL' -o formplayer.jar"
fi

if [ -f application.properties ]; then
    skip application.properties
else
    bad application.properties missing
    plan_add application.properties "curl -sSL '$FORMPLAYER_PROPS_URL' -o application.properties"
fi

# --- the plan ----------------------------------------------------------------

if [ "$(plan_count)" -gt 0 ]; then
    heading 'Plan'
    printf '%s' "$PLAN" | while IFS="$TAB" read -r label cmd; do
        [ -n "$label" ] || continue
        printf '    %-22s %s%s%s\n' "$label" "$DIM" "$cmd" "$RESET"
    done

    approved=false
    if $CHECK_ONLY; then
        printf '\n'
        info 'checking only; nothing above will be run'
    elif $ASSUME_YES; then
        approved=true
    elif [ ! -t 0 ]; then
        printf '\n'
        info 'no terminal for a prompt; re-run with --yes to approve'
    else
        printf '\n    %sInstall/run the %s item(s) above? [y/N]%s ' \
            "$BOLD" "$(plan_count)" "$RESET"
        read -r reply || reply=''
        case "$reply" in [yY]*) approved=true ;; esac
    fi

    if $approved; then
        printf '\n'
        while IFS="$TAB" read -r label cmd; do
            [ -n "$label" ] || continue
            run "$label" bash -c "$(declare -f register_compose_plugin); set -e; $cmd"
        done <<PLAN_EOF
$PLAN
PLAN_EOF
        # java and psql can be installed without landing on PATH, so re-resolve.
        # Both mutate PATH, so neither may be called in a command substitution.
        use_sdkman_java || true
        use_pg_keg || true

        # Installing docker-compose does not register it with the docker CLI, and
        # on a cold machine the plugin directory did not exist during inspection,
        # so nothing could be planned then. Register it now that it is there,
        # otherwise `docker compose` still fails and every service step below it
        # collapses.
        if ! docker compose version >/dev/null 2>&1; then
            plugin_dir=''
            if have brew && p=$(brew --prefix 2>/dev/null) && [ -d "$p/lib/docker/cli-plugins" ]; then
                plugin_dir="$p/lib/docker/cli-plugins"
            fi
            if [ -n "$plugin_dir" ]; then
                run 'docker compose' register_compose_plugin "$plugin_dir"
                if docker compose version >/dev/null 2>&1; then
                    ok 'docker compose' "$(docker compose version --short 2>/dev/null | head -1 || true)"
                else
                    bad 'docker compose' 'still not resolving after registering the plugin'
                    pending 'docker compose' 'see DEV_SETUP_MAC.md#container-engines'
                fi
            fi
        fi
    else
        while IFS="$TAB" read -r label cmd; do
            [ -n "$label" ] || continue
            pending "$label" "$cmd"
        done <<PLAN_EOF
$PLAN
PLAN_EOF
    fi
fi

# --- repository --------------------------------------------------------------

heading Repository

if git submodule status | grep -qE '^-'; then
    bad submodules 'not initialized'
    do_step submodules 'git submodule update --init --recursive' \
        git submodule update --init --recursive
else
    skip submodules
fi

if [ -x git-hooks/install.sh ] && [ ! -e .git/hooks/pre-commit ]; then
    bad 'git hooks' 'not installed'
    do_step 'git hooks' 'git-hooks/install.sh' ./git-hooks/install.sh
else
    skip 'git hooks'
fi

if ! have uv; then
    pending 'python deps' 'install uv, then uv sync --compile-bytecode'
elif [ -x "$VENV_PY" ] && $CHECK_ONLY; then
    # A run syncs anyway (cheap when current, and catches a stale venv after a
    # pull), but an existing venv is not something --check should flag.
    skip 'python deps' '.venv present'
else
    [ -x "$VENV_PY" ] || bad 'python deps' 'no .venv'
    do_step 'python deps' 'uv sync --compile-bytecode' uv sync --compile-bytecode
fi

# These go through run() rather than being called directly so that a failure is
# recorded and the run continues, instead of set -e ending it here.
if [ -f localsettings.py ]; then
    skip localsettings.py
else
    do_step localsettings.py 'cp localsettings.example.py localsettings.py' \
        cp localsettings.example.py localsettings.py
fi

if [ -d sharedfiles ]; then
    skip sharedfiles/
else
    do_step sharedfiles/ 'mkdir sharedfiles' mkdir -p sharedfiles
fi

manage() { "$VENV_PY" manage.py "$@"; }

# --- services, databases, and the rest ---------------------------------------
#
# These need both the virtualenv and a reachable daemon. Rather than stopping,
# note what is missing and let the summary report the rest.

REST_OK=true
if [ ! -x "$VENV_PY" ]; then
    REST_OK=false
    pending 'remaining steps' 'need a working virtualenv; fix the items above and re-run'
fi
if ! docker info >/dev/null 2>&1; then
    REST_OK=false
    pending 'remaining steps' 'need a running docker daemon; fix the items above and re-run'
fi
if ! docker compose version >/dev/null 2>&1; then
    # Without this, ./scripts/docker starts nothing and every database and
    # elasticsearch step below fails for a reason that looks unrelated.
    REST_OK=false
    pending 'remaining steps' 'need `docker compose` to resolve; see DEV_SETUP_MAC.md#container-engines'
fi

if $REST_OK; then
    heading Services

    expected_services=$(echo $SERVICES | wc -w | tr -d ' ')
    count_services() {
        docker ps ${1:+--filter health=$1} --format '{{.Names}}' 2>/dev/null | grep -c hqservice || true
    }

    if [ "$(count_services)" -ge "$expected_services" ]; then
        skip containers "$(count_services) running"
    elif acting; then
        run containers ./scripts/docker up -d $SERVICES
        # Verify state rather than trusting the exit code: check the containers
        # exist before waiting on their health, or a compose failure turns into a
        # five minute wait for containers that were never created.
        if [ "$(count_services)" -eq 0 ]; then
            bad containers 'no containers were created'
            info 'docker compose started nothing; see the log for what it reported'
            fail_add containers
        else
            start=$SECONDS
            while [ "$(count_services healthy)" -lt "$expected_services" ] \
                  && [ $((SECONDS - start)) -lt 300 ]; do
                if [ -n "$CLEAR" ]; then
                    printf '%s  %s·%s %-22s %s%s healthy, %s%s' "$CLEAR" "$CYAN" "$RESET" \
                        'health' "$DIM" "$(count_services healthy)/$expected_services" \
                        "$(elapsed "$start")" "$RESET"
                fi
                sleep 5
            done
            [ -n "$CLEAR" ] && printf '%s' "$CLEAR"
            if [ "$(count_services healthy)" -ge "$expected_services" ]; then
                ok containers "$(count_services healthy) healthy"
            else
                warn containers "$(count_services healthy) of $expected_services healthy after $(elapsed "$start")"
                info 'kafka is often the holdout: ./scripts/docker restart kafka'
            fi
        fi
    else
        bad containers "$(count_services) of $expected_services running"
        pending containers "./scripts/docker up -d $SERVICES"
    fi

    heading Databases

    if ! have psql; then
        pending 'formplayer db' 'needs the postgres client'
    elif PGPASSWORD=commcarehq psql -h localhost -U commcarehq -lqt 2>/dev/null \
            | cut -d'|' -f1 | grep -qw formplayer; then
        skip 'formplayer db'
    else
        bad 'formplayer db' missing
        do_step 'formplayer db' 'createdb formplayer -U commcarehq -h localhost' \
            env PGPASSWORD=commcarehq createdb formplayer -U commcarehq -h localhost
    fi

    # Both are idempotent, so they run every time rather than being probed.
    if acting; then
        run 'couch views' manage sync_couch_views
        run 'kafka topics' manage create_kafka_topics
    else
        info 'would run sync_couch_views and create_kafka_topics (both idempotent)'
    fi

    if manage migrate --check >/dev/null 2>&1; then
        skip migrations 'up to date'
    elif acting; then
        bad migrations pending
        # CCHQ_IS_FRESH_INSTALL skips migrations that only matter to existing
        # data. It is only correct on a brand new database.
        plan=$(manage showmigrations --plan 2>/dev/null || true)
        if ! printf '%s' "$plan" | grep -q '^\[X\]'; then
            info 'fresh database: using CCHQ_IS_FRESH_INSTALL=1'
            run migrations env CCHQ_IS_FRESH_INSTALL=1 "$VENV_PY" manage.py migrate --noinput
        else
            run migrations manage migrate --noinput
        fi
    else
        bad migrations pending
        pending migrations 'CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput'
    fi

    heading Elasticsearch

    es_indices() { curl -s -m 5 'localhost:9200/_cat/indices?h=index' 2>/dev/null | grep -c . || true; }

    if [ "$(es_indices)" -gt 0 ]; then
        skip indices "$(es_indices) present"
    else
        bad indices none
        do_step indices './manage.py ptop_preindex' manage ptop_preindex
    fi

    heading 'Front end'

    if [ -d node_modules ]; then
        skip 'js deps'
    elif ! have yarn; then
        pending 'js deps' 'needs yarn'
    else
        bad 'js deps' 'not installed'
        do_step 'js deps' 'yarn install --frozen-lockfile' yarn install --frozen-lockfile
    fi

    if acting; then
        run 'js translations' manage compilejsi18n
    else
        info 'would run compilejsi18n'
    fi

    heading 'Application data'

    # get_all_versions reports builds actually in the database, unlike
    # get_default_build_spec, which reads a config document that can exist without them.
    has_build=$(manage shell -c "
from corehq.apps.builds.utils import get_all_versions
try:
    print('yes' if get_all_versions([]) else 'no')
except Exception:
    print('unknown')
" 2>/dev/null | tail -1 || echo unknown)

    case "$has_build" in
        yes) skip 'commcare build' ;;
        no)
            bad 'commcare build' 'none installed'
            do_step 'commcare build' './manage.py add_commcare_build --latest' \
                manage add_commcare_build --latest
            ;;
        *)
            warn 'commcare build' 'could not determine'
            pending 'commcare build' './manage.py add_commcare_build --latest'
            ;;
    esac

    has_superuser=$(manage shell -c "
from django.contrib.auth.models import User
print('yes' if User.objects.filter(is_superuser=True).exists() else 'no')
" 2>/dev/null | tail -1 || echo unknown)

    if [ "$has_superuser" = yes ]; then
        skip superuser 'one already exists'
    elif acting && [ -t 0 ]; then
        # make_superuser prompts for a password itself, so it needs a terminal
        # and must not have its output redirected.
        printf '    %sSuperuser email (blank to skip):%s ' "$DIM" "$RESET"
        read -r su_email || su_email=''
        if [ -n "$su_email" ]; then
            manage make_superuser "$su_email" || { bad superuser 'make_superuser failed'; fail_add superuser; }
        else
            skip superuser skipped
        fi
    else
        bad superuser none
        pending superuser './manage.py make_superuser <email>'
    fi

    heading 'Services check'
    # check_services exits non-zero when any service is down, so capture its
    # output first: piping it directly would trip pipefail.
    services_out=$(manage check_services 2>/dev/null | strip_color | grep -E 'SUCCESS|FAILURE' || true)
    if [ -n "$services_out" ]; then
        printf '%s\n' "$services_out" | sed 's/^/  /'
        if printf '%s' "$services_out" | grep -q FAILURE; then
            info 'celery and formplayer report FAILURE until started, see Next steps'
        fi
    else
        warn check_services 'could not run'
    fi
fi

# --- summary -----------------------------------------------------------------

if [ -n "$FAILED" ]; then
    heading 'Failed'
    printf '%s' "$FAILED"
    info "full output: $LOG_FILE"
fi

if [ -n "$PENDING" ]; then
    heading 'To do by hand'
    printf '%s' "$HINTS"
fi

problems=$(( $(count_lines "$FAILED") + $(count_lines "$PENDING") ))

if $CHECK_ONLY; then
    printf '\n'
    if [ "$problems" -gt 0 ]; then
        printf '  %s%s item(s) need attention.%s\n\n' "$YELLOW" "$problems" "$RESET"
        exit 1
    fi
    printf '  %sEnvironment looks complete.%s\n\n' "$GREEN" "$RESET"
    exit 0
fi

heading 'Next steps'
cat <<'EOF'
  Two terminals. First, the support processes (webpack, celery, formplayer):

    uvx honcho start -f Procfile.dev

  Then Django on its own, so breakpoint()/pdb has a terminal to itself and you
  can restart the app without cycling the rest:

    uv run ./manage.py runserver localhost:8000

  Then open http://localhost:8000

  Re-run this script any time; it skips what is already done.
  scripts/setup-dev.sh --check reports state without changing anything.
EOF

if [ "$problems" -gt 0 ]; then
    printf '\n  %s%s item(s) need attention; the environment is incomplete.%s\n\n' \
        "$YELLOW" "$problems" "$RESET"
    exit 1
fi
printf '\n'
