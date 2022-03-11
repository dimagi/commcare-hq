# Get total count of python dependencies and outdated python dependencies

total_python_deps="$(pip list| wc -l)"
outdated_python_deps="$(pip list --outdated| wc -l)"

# Get outdated JS dependency count

COUNT_OUTDATED_DEP_CODE=$(cat <<-END
import json
import sys

dep_arr = json.load(sys.stdin)
print(len(dep_arr["data"]["body"]))

END
)

outdated_js_deps="$(yarn outdated --json | sed -n 2p | python -c "$COUNT_OUTDATED_DEP_CODE")"


# Get total JS dependencies from package.json
COUNT_DEP_CODE=$(cat <<-END
import json
import sys

file = open('package.json', 'r')
file_obj=json.load(file)

deps= len(file_obj["dependencies"].keys())
dev_deps = len(file_obj["devDependencies"].keys())
print(deps+dev_deps)

file.close()
END
)
total_js_deps="$(python -c "$COUNT_DEP_CODE")"

# Publish metrics to Datadog

source scripts/datadog-utils.sh

send_metric_to_datadog "commcarehq.dependency.python.total" $total_python_deps "count"
send_metric_to_datadog "commcarehq.dependency.js.outdated" $outdated_python_deps "count"


send_metric_to_datadog "commcarehq.dependency.js.total" $total_js_deps "count"
send_metric_to_datadog "commcarehq.dependency.js.outdated" $outdated_js_deps "count"
