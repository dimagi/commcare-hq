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

function list-html() {
  find corehq custom -name '*.html' | grep -v 'vellum'
}

## Count files that haven't met migration criteria

function list-html-with-inline-scripts() {
  list-html | xargs grep -l '<script>'
}

function list-js-without-hqDefine() {
  list-no-esm-js | xargs grep -L 'hqDefine'
}

# Partial indicator of RequireJS work left: how many js files don't yet use
# the variation of hqDefine that specifies dependencies?
function list-js-without-requirejs() {
  list-no-esm-js | xargs grep -L 'hqDefine.*\['
}

# The other indicator of RequireJS work left: how many HTML files still have script tags?
function list-html-with-external-scripts() {
  list-html | xargs grep -l 'script.*src='
}

## Calculate migrated percentage for given statistic
function percent() {
  result=$(echo "100 - $1 * 100 / $2" | bc)
  echo -e "$result%\t($(($2 - $1))/$2)"
}


## Main script

command=${1:-""}
help="Pass list-script, list-hqdefine, list-requirejs, or list-requirejs-html to list the files that have yet to be migrated. list-esm to list ESM formatted files"

jsTotalCount=$(echo $(list-js | wc -l))
noEsmJsTotalCount=$(echo $(list-no-esm-js | wc -l))
htmlTotalCount=$(echo $(list-html | wc -l))

case $command in

  "list-script" )
    echo "The following templates still have inline script tags:"
    list-html-with-inline-scripts | sed 's/^/  /'
    ;;

  "list-esm" )
    echo "These files use ESM syntax:"
    list-esm-js | sed 's/^/  /'
    ;;

  "list-hqdefine" )
    echo "The following files do not use hqDefine:"
    list-js-without-hqDefine | sed 's/^/  /'
    ;;

  "list-requirejs" )
    echo "The following modules do not specify their dependencies:"
    list-js-without-requirejs | sed 's/^/  /'
    ;;

  "list-requirejs-html" )
    echo "The following templates still have external script tags:"
    list-html-with-external-scripts | sed 's/^/  /'
    ;;

  # For use with static_analysis management command
  "static-analysis" )
    withoutHqDefineCount=$(echo $(list-js-without-hqDefine | wc -l))
    withoutRequireJsCount=$(echo $(list-js-without-requirejs | wc -l))
    echo "$withoutHqDefineCount $(($withoutRequireJsCount - $withoutHqDefineCount)) $(($noEsmJsTotalCount - $withoutRequireJsCount))"
    ;;

  "")
    # No command passed; print total migration progress
    # Don't bother printing the HTML external script percentage as a metric; it's misleading
    echo

    unmigratedCount=$(echo $(list-html-with-inline-scripts | wc -l))
    echo "$(percent $unmigratedCount $htmlTotalCount) of HTML files are free of inline scripts"

    unmigratedCount=$(echo $(list-js-without-hqDefine | wc -l))
    echo "$(percent $unmigratedCount $noEsmJsTotalCount) of non-ESM JS files use hqDefine"

    unmigratedCount=$(echo $(list-js-without-requirejs | wc -l))
    echo "$(percent $unmigratedCount $noEsmJsTotalCount) of non-ESM JS files specify their dependencies"

    unmigratedCount=$(echo $(list-html-with-external-scripts | wc -l))
    echo "$(percent $unmigratedCount $htmlTotalCount) of HTML files are free of script tags"

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
