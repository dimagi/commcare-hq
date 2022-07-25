# Get total count of python dependencies and outdated python dependencies

# skip 2 header lines (produced by pip list)
total_python_deps="$(pip list | tail -n +3 | wc -l)"
# skip 1 header line (produced by outdated-dependency-metrics.py)
outdated_python_deps_list="$(pip list --format json --outdated | ./scripts/outdated-dependency-metrics.py pip | tail -n +2)"
outdated_python_deps=$(echo "${outdated_python_deps_list}" | wc -l)
multi_major_outdated_python_deps=$(echo "${outdated_python_deps_list}" | grep '^[^01]' | wc -l)
major_outdated_python_deps=$(echo "${outdated_python_deps_list}" | grep '^1' | wc -l)
minor_outdated_python_deps=$(echo "${outdated_python_deps_list}" | grep '^0\.[^0]' | wc -l)
patch_outdated_python_deps=$(echo "${outdated_python_deps_list}" | grep '^0\.0\.[^0]' | wc -l)

# Get outdated JS dependency count

function outdated_count {
    python - <(cat -) <<-END
import json
import sys
with open(sys.argv[1], "r") as json_file:
    dep_arr = json.load(json_file)
print(len(dep_arr["data"]["body"]))
END
}

outdated_js_deps="$(yarn outdated --json | sed -n 2p | outdated_count)"


# Get total JS dependencies from package.json

function dependency_count {
    local json_path="$1"
    python - "$json_path" <<-END
import json
import sys

with open(sys.argv[1], "r") as json_file:
    packages = json.load(json_file)

print(sum(len(packages[k]) for k in ["dependencies", "devDependencies"]))
END
}

total_js_deps=$(dependency_count package.json)

# Publish metrics to Datadog

source scripts/datadog-utils.sh

send_metric_to_datadog "commcare.static_analysis.dependency.python.total" $total_python_deps "gauge"
send_metric_to_datadog "commcare.static_analysis.dependency.python.outdated" $outdated_python_deps "gauge"
send_metric_to_datadog "commcare.static_analysis.dependency.python.multi_major_outdated" $multi_major_outdated_python_deps "gauge"
send_metric_to_datadog "commcare.static_analysis.dependency.python.major_outdated" $major_outdated_python_deps "gauge"
send_metric_to_datadog "commcare.static_analysis.dependency.python.minor_outdated" $minor_outdated_python_deps "gauge"
send_metric_to_datadog "commcare.static_analysis.dependency.python.patch_outdated" $patch_outdated_python_deps "gauge"


send_metric_to_datadog "commcare.static_analysis.dependency.js.total" $total_js_deps "gauge"
send_metric_to_datadog "commcare.static_analysis.dependency.js.outdated" $outdated_js_deps "gauge"
