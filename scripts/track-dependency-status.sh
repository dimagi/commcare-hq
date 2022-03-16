# Get total count of python dependencies and outdated python dependencies

total_python_deps="$(pip list| wc -l)"
outdated_python_deps="$(pip list --outdated| wc -l)"

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


send_metric_to_datadog "commcare.static_analysis.dependency.js.total" $total_js_deps "gauge"
send_metric_to_datadog "commcare.static_analysis.dependency.js.outdated" $outdated_js_deps "gauge"
