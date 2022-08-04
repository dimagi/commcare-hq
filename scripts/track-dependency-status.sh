#!/usr/bin/env bash

set -e

# import the datadog utils
source ./scripts/datadog-utils.sh

send_to_datadog=true


function main {
    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                usage
                return 0
                ;;
            -n|--dry-run)
                echo "[DRY RUN] no metrics will be sent to datadog" >&2
                # I would rather not use a global for this, but passing it two
                # function calls deep feels messier in this case.
                send_to_datadog=false
                ;;
            *)
                usage "invalid args: $*"
                return 1
                ;;
        esac
        shift
    done
    local total=0

    # get total Python dependency count (skip 2 header lines)
    log_msg_with_time INFO "calculating Python package metrics"
    total=$(pip list 2>/dev/null | tail -n +3 | wc -l)
    # publish python metrics
    pip list --format json --outdated 2>/dev/null | publish_metrics python pip "$total"

    # get total JS dependency count (skip the first header line)
    log_msg_with_time INFO "calculating JS package metrics"
    total=$(./scripts/yarn-list.py | tail -n +2 | wc -l)
    # publish javascript metrics
    ./scripts/yarn-list.py --outdated --json | publish_metrics js yarn-list "$total"

    log_msg_with_time INFO "done"
}


function publish_metrics {
    local metric_id="$1"
    local data_format="$2"
    local total="$3"

    local metric_prefix="commcare.static_analysis.dependency.${metric_id}"
    local stats=$(cat - | ./scripts/outdated-dependency-metrics.py "$data_format" --stats)

    local outdated=$(outdated_stat Outdated "$stats")
    local multmajor=$(outdated_stat Multi-Major "$stats")
    local major=$(outdated_stat Major "$stats")
    local minor=$(outdated_stat Minor "$stats")
    local patch=$(outdated_stat Patch "$stats")
    local exotic=$(outdated_stat Exotic "$stats")

    publish_datadog_gauge "${metric_prefix}.total" "$total"
    publish_datadog_gauge "${metric_prefix}.outdated" "$outdated"
    publish_datadog_gauge "${metric_prefix}.multi_major_outdated" "$multmajor"
    publish_datadog_gauge "${metric_prefix}.major_outdated" "$major"
    publish_datadog_gauge "${metric_prefix}.minor_outdated" "$minor"
    publish_datadog_gauge "${metric_prefix}.patch_outdated" "$patch"
    publish_datadog_gauge "${metric_prefix}.exotic_outdated" "$exotic"
}


function outdated_stat {
    local label="$1"
    local stats="$2"
    echo "$stats" | grep -E "^${label}: " | awk -F': ' '{print $2}'
}


function publish_datadog_gauge {
    local metric_path="$1"
    local value="$2"
    echo "$metric_path == $value"
    if $send_to_datadog; then
        send_metric_to_datadog "$metric_path" "$value" gauge
    fi
}


function log_msg_with_time {
    local level_name="$1"; shift
    local msg="$*"
    local now=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${now}] ${level_name}: $msg" >&2
}


function usage {
    local script=$(basename "$0")
    local msg="$*"
    echo "USAGE: $script [-h|--help] [-n|--dry-run]" >&2
    if [ -n "$msg" ]; then
        echo "ERROR: $msg" >&2
    fi
}


main "$@"
