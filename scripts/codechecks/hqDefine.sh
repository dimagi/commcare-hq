#!/bin/bash
# run as
# scripts/codechecks/hqDefine.sh

function list-js() {
  find corehq -name '*.js' | grep -v '/_design/' | grep -v 'couchapps' | grep -v '/js/vellum/'
}

function list-js-with-hqDefine() {
  list-js | xargs grep -l 'hqDefine'
}

function list-js-without-hqDefine() {
  list-js | xargs grep -L 'hqDefine'
}

jsWithHqDefineCount=$(echo $(list-js-with-hqDefine | wc -l))
jsTotalCount=$(echo $(list-js | wc -l))
percent=$(python -c "print '%d%%' % int($jsWithHqDefineCount * 100./$jsTotalCount)")
echo "$percent "'('"$jsWithHqDefineCount/$jsTotalCount"')'" of JS files use hqDefine"
echo
echo "The following files do not use hqDefine:"
list-js-without-hqDefine | sed 's/^/  /'
