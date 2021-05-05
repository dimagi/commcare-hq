#!/usr/bin/env bash
set -e

CURRENT_TIME=$(date +%s)

# This script calculates code quality metrics.
# These are evaluated in the daily travis build and reported to datadog.
# Other metrics are computed in the management command `report_code_metrics`

function send_metric_to_datadog() {
    if [ -z "$DATADOG_API_KEY" ]; then
        return
    fi

    curl  -X POST -H "Content-type: application/json" \
          -d "{ \"series\" :
             [{\"metric\":\"$1\",
              \"points\":[[$CURRENT_TIME, $2]],
              \"type\":\"$3\",
              \"host\":\"travis-ci.org\",
              \"tags\":[
                \"environment:travis\",
                \"travis_build:$TRAVIS_BUILD_ID\",
                \"travis_number:$TRAVIS_BUILD_NUMBER\",
                \"travis_job_number:$TRAVIS_JOB_NUMBER\"
              ]}
             ]
        }" \
          "https://app.datadoghq.com/api/v1/series?api_key=${DATADOG_API_KEY}" || true
}

RADON_METRICS_FILENAME="radon-code-metrics.txt"

# Run code complexity metrics on ., drop ANSI escape codes, and save to a file
radon cc . --min=C --total-average --exclude='node_modules/*,staticfiles/*' \
    | sed 's/\x1B\[[0-9;]\{1,\}[A-Za-z]//g' \
    > $RADON_METRICS_FILENAME

TOTAL_BLOCKS=$(grep 'blocks.*analyzed' $RADON_METRICS_FILENAME | grep -oE '[0-9]+')
COMPLEXITY=$(grep 'Average.complexity' $RADON_METRICS_FILENAME | grep -oE '[0-9.]+' | head -c 5)

echo "Average complexity:" $COMPLEXITY
echo $TOTAL_BLOCKS "blocks analyzed"
echo "Number of blocks below a 'B' grade:"

for GRADE in "C" "D" "E" "F"; do
    NUM_BLOCKS=$(cat $RADON_METRICS_FILENAME | grep " - $GRADE$" | wc -l)
    echo " " $GRADE ":" $NUM_BLOCKS
done

if [[ "$1" == "datadog" ]]; then
    send_metric_to_datadog "commcare.gtd.avg_complexity" $COMPLEXITY "gauge"
    send_metric_to_datadog "commcare.gtd.code_blocks" $TOTAL_BLOCKS "gauge"
fi

rm $RADON_METRICS_FILENAME
