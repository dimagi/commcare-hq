#!/usr/bin/env bash
set -e

# This script calculates code quality metrics.
# These are evaluated in the daily travis build and reported to datadog.
# Other metrics are computed in the management command `static_analysis`

source scripts/datadog-utils.sh  # provides send_metric_to_datadog

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
    send_metric_to_datadog "commcare.static_analysis.avg_complexity" $COMPLEXITY "gauge"
    send_metric_to_datadog "commcare.static_analysis.code_blocks" $TOTAL_BLOCKS "gauge"
fi

rm $RADON_METRICS_FILENAME
