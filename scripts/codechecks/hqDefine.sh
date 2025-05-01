#!/bin/bash
# run as
# scripts/codechecks/hqDefine.sh

## Count files by type

function list-js() {
  find corehq custom -name '*.js' | grep -v '/_design/' | grep -v 'couchapps' | grep -v '/js/vellum/'
}

function list-no-esm-js() {
  list-js | xargs grep -L '^import.*;'
}

function list-esm-js() {
  list-js | xargs grep -l '^import.*;'
}

## Count files that haven't met migration criteria

function list-js-without-hqDefine() {
  list-no-esm-js | xargs grep -L 'hqDefine'
}

## Calculate migrated percentage for given statistic
function percent() {
  result=$(echo "100 - $1 * 100 / $2" | bc)
  echo -e "$result%\t($(($2 - $1))/$2)"
}


## Main script

command=${1:-""}
help="Pass list-hqdefine to list the files that have yet to be migrated. list-esm to list ESM formatted files"

jsTotalCount=$(echo $(list-js | wc -l))
noEsmJsTotalCount=$(echo $(list-no-esm-js | wc -l))
esmJsTotalCount=$((jsTotalCount - noEsmJsTotalCount))

case $command in

  "list-esm" )
    echo "These files use ESM syntax:"
    list-esm-js | sed 's/^/  /'
    ;;

  "list-hqdefine" )
    echo "The following files do not use hqDefine:"
    list-js-without-hqDefine | sed 's/^/  /'
    ;;

  # For use with static_analysis management command
  "static-analysis" )
    noEsmCount=$(echo $(list-no-esm-js | wc -l))
    echo "$esmJsTotalCount $noEsmJsTotalCount"
    ;;

  "")
    # No command passed; print total migration progress
    echo

    unmigratedCount=$(echo $(list-js-without-hqDefine | wc -l))
    echo "$(percent $unmigratedCount $noEsmJsTotalCount) of non-ESM JS files use hqDefine"

    unmigratedCount=$(echo $(list-no-esm-js | wc -l))
    echo "$(percent $unmigratedCount $jsTotalCount) of JS files use ESM format"

    echo
    echo $help
    ;;
  *)
    echo "Unrecognized command"
    echo $help
    ;;
esac 
