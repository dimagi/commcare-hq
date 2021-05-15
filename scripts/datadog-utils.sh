#!/bin/bash

# Accepts three arguments: metric name, value, and type (gauge, count, or rate)
# Usage:
#   send_metric_to_datadog "commcare.foo.bar" 7 "gauge"
# or with optional "tag" argument:
#   send_metric_to_datadog "commcare.foo.bar" 7 "gauge" "domain:foo"
function send_metric_to_datadog() {
    if [ -z "$DATADOG_API_KEY" -o -z "$DATADOG_APP_KEY" ]; then
        return
    fi

    EXTRA_TAG=""
    if [[ "$4" ]]; then
        EXTRA_TAG="\"$4\","
    fi

    currenttime=$(date +%s)
    curl  -X POST \
          -H "Content-type: application/json" \
          -H "DD-API-KEY: ${DATADOG_API_KEY}" \
          -H "DD-APP-KEY: ${DATADOG_APP_KEY}" \
          -d "{ \"series\" :
                [{\"metric\":\"$1\",
                  \"points\":[[$currenttime, $2]],
                  \"type\":\"$3\",
                  \"host\":\"travis-ci.org\",
                  \"tags\":[
                    $EXTRA_TAG
                    \"environment:travis\",
                    \"travis_build:$TRAVIS_BUILD_ID\",
                    \"travis_number:$TRAVIS_BUILD_NUMBER\",
                    \"travis_job_number:$TRAVIS_JOB_NUMBER\",
                    \"partition:$NOSE_DIVIDED_WE_RUN\"
                  ]}
                ]
              }" \
          "https://app.datadoghq.com/api/v1/series" || true
}
