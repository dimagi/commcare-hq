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

    if [ -n "$TRAVIS" ]; then
      HOST=travis-ci.org
      CI_ENV=travis
    elif [ -n "$GITHUB_ACTIONS" ]; then
      HOST=github.com
      CI_ENV=github_actions
    else
      HOST=unknown
      CI_ENV=unknown
    fi

    currenttime=$(date +%s)
    curl  -s \
          -X POST \
          -H "Content-type: application/json" \
          -H "DD-API-KEY: ${DATADOG_API_KEY}" \
          -H "DD-APP-KEY: ${DATADOG_APP_KEY}" \
          -d "{ \"series\" :
                [{\"metric\":\"$1\",
                  \"points\":[[$currenttime, $2]],
                  \"type\":\"$3\",
                  \"host\":\"$HOST\",
                  \"tags\":[
                    $EXTRA_TAG
                    \"environment:$CI_ENV\",
                    \"partition:$DIVIDED_WE_RUN\"
                  ]}
                ]
              }" \
          "https://app.datadoghq.com/api/v1/series" >/dev/null || true
}
