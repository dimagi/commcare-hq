#!/usr/bin/env bash
set -e

# This script calculates code quality metrics.

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

rm $RADON_METRICS_FILENAME
