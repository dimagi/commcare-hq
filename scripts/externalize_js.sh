#!/bin/sh

# PURPOSE:
# Externalizing JS is a fairly manual process that has to happen
# on a couple hundred files. Hopefully this will simplify that process

# It creates a new file, places whatever was in the js-inline
# script tags in the new file, and adds the new necessary static import
# to the html file. This is then committed.
# Afterwards it checks for django template tags, deletes and replaces them
# with a few functions and prints out the newly needed initial_page_data tags

# TODOS:
#   auto indent the moved javascript

# USAGE:
# From the base level of this repo, run `./scripts/externalize_js.sh <app> <module>
# The first argument is the django app the module is located in.
# The second is the file name of the module.
# ex. `$ ./scripts/externalize_js.sh sms add_gateway`
# It isn't perfect, definitely check for lint and adjust the names around as desired.
# There are also a few lines printed by the script that may need to be placed in the code as directed
# Also make sure to visit the page(s) the module is used on to make sure they aren't borked!.

# TODOS:
#   auto indent the moved javascript


# strict mode --> kill it if something fails
set -euo pipefail

function abort () {
    echo $1
    echo "Aborting."
    exit 1
}

function should_continue () {
    select yn in "Yes" "No"; do
        case $yn in
            Yes ) break;;
            No ) abort "Sounds good.";;
        esac
    done
}

# GNU-sed is apparently much more powerful than the OSX standard,
# and there is at least one place where it's quite useful.
# Some regexes below won't function correctly without it.
has_gnu_sed=`sed --version | grep "GNU sed"`
if [[ ! $has_gnu_sed ]]; then
    echo "Hey! This script was written using GNU sed so it may not function quite as expected using your setup."
    echo "If you want to install GNU sed, please visit this link http://bfy.tw/GbIs"
    echo "Do you want to run the rest of the script anyway?"
    should_continue
fi


has_local_changes=`git diff-index HEAD` && true
if [[ $has_local_changes ]]; then
    abort "You have uncommitted changes in your working tree."
fi


APP=$1
MODULE=$2


branch=$(git rev-parse --abbrev-ref HEAD)
if [[ $branch == 'master' ]]; then
    echo "You must not be on master to run this command."
    echo "Create a new branch?"

    function branch() {
        read -p "What are your initials?" INITIALS
        git checkout -b $INITIALS/ejs/$APP-$MODULE
    }
    select yn in "Yes" "No"; do
        case $yn in
            Yes ) branch; break;;
            No ) abort "You must not be on master to run this command."
        esac
    done
fi


# formulate locations and names
HTML_FILE_LOCATION="./corehq/apps/$APP/templates/$APP/$MODULE.html"
NEW_MODULE_NAME="$APP/js/$MODULE"
NEW_MODULE_LOCATION="./corehq/apps/$APP/static/$APP/js/$MODULE.js"

if [ -f $NEW_MODULE_LOCATION ]; then
    echo "The new module has already been created.\nDo you want to continue?"
    should_continue
fi

# create file
touch $NEW_MODULE_LOCATION

# add boilerplate
echo "hqDefine('$NEW_MODULE_NAME', function() {" >> $NEW_MODULE_LOCATION

# pull inline js from file, removes the script tags, and places it into the new file
sed -n "/{% block js-inline %}/, /{% endblock\( js-inline\)\? %}/ p" $HTML_FILE_LOCATION | \
    python -c "import sys; sys.stdout.writelines(sys.stdin.readlines()[2:-2])" >> $NEW_MODULE_LOCATION

# remove from old file
sed -i "/{% block js-inline %}/, /{% endblock\( js-inline\)\? %}/ d" $HTML_FILE_LOCATION

# close off boilerplate
echo "});" >> $NEW_MODULE_LOCATION


# add import to the html
script_import="<script src=\"{% static '$NEW_MODULE_NAME.js' %}\"></script>"
count=$(sed -n "/{% block js %}/p" $HTML_FILE_LOCATION | wc -l)
# if there is a block js, add it inside at the end
if [ "$count" -gt 0 ]; then
    sed -i "/{% block js %}/,/{% endblock/ {
        /{% endblock/ i \\
        $script_import
    }" $HTML_FILE_LOCATION
# otherwise, just tell them to add one somewhere on the page
else
    echo "----------------------------"
    echo "Please add this static import somewhere in the html file"
    echo "{% block js %}{{ block.super }}\n\t<script src=\"{% static '$NEW_MODULE_NAME'.js %}\"></script>\n{% endblock %}"
    echo "----------------------------"
fi

# commit the blob movement
git add $NEW_MODULE_LOCATION $HTML_FILE_LOCATION
git commit -m "first pass externalizing javascript in $MODULE"

# check where in page there are template tags
OPEN_BRACKET_REGEX="{\(%\|{\)"
CLOSE_BRACKET_REGEX="\(%\|}\)}"
QUOTE="\('\|\"\)"
TEMPLATE_TAGS=`sed -n "/$OPEN_BRACKET_REGEX/=" $NEW_MODULE_LOCATION`
TEMPLATE_TAG_COUNT=`echo $TEMPLATE_TAGS | wc -l`
if [ "$TEMPLATE_TAG_COUNT" -gt 0 ]; then
    echo "----------------------------"
    echo "Please check template tags on these lines."
    echo $TEMPLATE_TAGS

    # convert translation tags first
    GETTEXT_OPEN="gettext("
    GETTEXT_CLOSE=")"
    sed -i "/$QUOTE$OPEN_BRACKET_REGEX trans/s/ $CLOSE_BRACKET_REGEX$QUOTE/$GETTEXT_CLOSE/; \
            s/$QUOTE$OPEN_BRACKET_REGEX trans /$GETTEXT_OPEN/" $NEW_MODULE_LOCATION

    # now move on to tags that require imports
    INITIALPAGEDATA_OPEN="initialPageData.get('"
    INITIAL_PAGE_DATA_CLOSE="')"

    INITIAL_PAGE_DATA_TAGS=`sed -n "s/.*$OPEN_BRACKET_REGEX//; s/ $CLOSE_BRACKET_REGEX.*//p" $NEW_MODULE_LOCATION`
    INITIAL_PAGE_DATA_TAG_LINES=`sed -n "/$OPEN_BRACKET_REGEX/=" $NEW_MODULE_LOCATION`
    TAG_COUNT=`echo $INITIAL_PAGE_DATA_TAGS | wc -l`
    if [ "$TAG_COUNT" -gt 0 ]; then
        sed -i "s/$OPEN_BRACKET_REGEX /$INITIALPAGEDATA_OPEN/; \
                s/ $CLOSE_BRACKET_REGEX/$INITIAL_PAGE_DATA_CLOSE/" $NEW_MODULE_LOCATION
        INITIALPAGEDATA_IMPORT="var initialPageData = hqImport('hqwebapp\/js\/initial_page_data')\;"
        sed -i "/hqDefine/a \
                $INITIALPAGEDATA_IMPORT" $NEW_MODULE_LOCATION
        echo "and in particular these lines"
        echo $INITIAL_PAGE_DATA_TAG_LINES
        echo "and add these data imports as well"
        for ipd in $INITIAL_PAGE_DATA_TAGS; do
            echo "{% initial_page_data '$ipd' $ipd %}"
        done
    fi
    echo "----------------------------"
fi


# a bit more yelling at the user
# (maybe should just open these in an available browser? todo)
./manage.py show_urls | grep $MODULE
echo "----------------------------"
echo "^^^^^^ Check to see if this/these page(s) works"
echo "----------------------------"
