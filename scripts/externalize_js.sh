#!/bin/sh

# PURPOSE:
# Externalizing JS is a fairly manual process that has to happen
# on a couple hundred files. Hopefully this will simplify that process

# For now, it creates the new file, places whatever was in the js-inline
# script tags in the new file, and adds the new necessary static import
# to the html file.

# TODOS:
#   check for template tags in the js file
#       print necessary initial page data
#       actually add initial page data tags
#       convert tags to requesting initial page data
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
if [[ $has_gnu_sed ]]; then
    echo "Hey! This script was written using GNU sed so it may not function quite as expected using your setup."
    echo "If you want to install GNU sed, please visit this link http://bfy.tw/GbIs"
    echo "Do you want to run the rest of the script anyway?"
    should_continue
fi

has_local_changes=`git diff-index HEAD` && true
if [[ $has_local_changes ]]
then
    abort "You have uncommitted changes in your working tree."
fi

branch=$(git rev-parse --abbrev-ref HEAD)
if [[ $branch == 'master' ]]
then
    abort "You must not be on master to run this command."
fi

app=$1
module=$2

# formulate locations and names
html_file_location="./corehq/apps/$app/templates/$app/$module.html"
new_module_name="$app/js/$module"
new_module_location="./corehq/apps/$app/static/$app/js/$module.js"

if [ -f $new_module_location ]; then
    echo "The new module has already been created.\nDo you want to continue?"
    should_continue
fi

# create file
touch $new_module_location

# add boilerplate
echo "hqDefine('$new_module_name', function() {" >> $new_module_location

# pull inline js from file, removes the script tags, and places it into the new file
sed -n "/{% block js-inline %}/, /{% endblock\( js-inline\)\? %}/ p" $html_file_location | \
    python -c "import sys; sys.stdout.writelines(sys.stdin.readlines()[2:-2])" >> $new_module_location

# remove from old file
sed -i "/{% block js-inline %}/, /{% endblock\( js-inline\)\? %}/ d" $html_file_location

# close off boilerplate
echo "});" >> $new_module_location


# add import to the html
script_import="<script src=\"{% static '$new_module_name.js' %}\"></script>"
count=$(sed -n "/{% block js %}/p" $html_file_location | wc -l)
# if there is a block js, add it inside at the end
if [ "$count" -gt 0 ]; then
    sed -i "/{% block js %}/,/{% endblock/ {
        /{% endblock/ i \\
        $script_import
    }" $html_file_location
# otherwise, just tell them to add one somewhere on the page
else
    echo "----------------------------"
    echo "Please add this static import somewhere in the html file"
    echo "{% block js %}{{ block.super }}\n\t<script src='{% static "$new_module_name".js %}'></script>\n{% endblock %}"
    echo "----------------------------"
fi

# commit the blob movement
git add $new_module_location $html_file_location
git commit -m "first pass externalizing javascript in $module"


# a bit more yelling at the user
# (maybe should just open these in an available browser? todo)
./manage.py show_urls | grep $module
echo "----------------------------"
echo "^^^^^^ Check to see if this/these page(s) works"
echo "----------------------------"


# check where in page there are template tags
template_tags=`sed -n "/{%/=; /{{/=" $new_module_location`
template_tag_count=`echo $template_tags | wc -l`
if [ "$template_tag_count" -gt 0 ]; then
    echo "----------------------------"
    echo "Please fix template tags on these lines."
    echo $template_tags
    echo "----------------------------"
fi
