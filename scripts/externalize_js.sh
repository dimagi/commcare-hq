#!/bin/sh

# TODOS:
#   check for template tags in the js file
#       print necessary initial page data
#       actually add initial page data tags
#       convert tags to requesting initial page data
#   auto indent the moved javascript

app=$1
module=$2

# formulate locations and names
html_file_location="./corehq/apps/$app/templates/$app/$module.html"
new_module_name="$app/js/$module"
new_module_location="./corehq/apps/$app/static/$app/js/$module.js"


# create file
touch $new_module_location

# add boilerplate
echo "hqDefine('$new_module_name', function() {" >> $new_module_location

# check if there is an endblock specifically for js-inline and handle accordingly
count=$(sed -n "/{% endblock js-inline %}/p" $html_file_location | wc -l)
if [ "$count" -gt 0 ]; then
    # pull inline js from file, removes the script tags, and places it into the new file
    sed -n "/{% block js-inline %}/, /{% endblock js-inline %}/ p" $html_file_location | sed -n "3,$ p" >> $new_module_location

    # remove from old file
    sed -i "" '/{% block js-inline %}/, /{% endblock js-inline %}/ d' $html_file_location
else
    # pull inline js from file, removes the script tags, and places it into the new file
    sed -n "/{% block js-inline %}/, /{% endblock %}/ p" $html_file_location | sed -n "3,$ p" >> $new_module_location

    # remove from old file
    sed -i "" '/{% block js-inline %}/, /{% endblock %}/ d' $html_file_location
fi

# removes the last two lines (which are script and endblock tags)
sed -i "" '$d' $new_module_location
sed -i "" '$d' $new_module_location

# close off boilerplate
echo "});" >> $new_module_location


# add import to the html
script_import="<script src=\"{% static '$new_module_name.js' %}\"></script>"
count=$(sed -n "/{% block js %}/p" $html_file_location | wc -l)
# if there is a block js, add it inside
if [ "$count" -gt 0 ]; then
    sed -i "" "/{% block js %}/a\\
    $script_import
    " $html_file_location
# otherwise, just tell them to add one somewhere on the page
else
    echo "----------------------------"
    echo "Please add this static import somewhere in the html file"
    echo "{% block js %}{{ block.super }}\n<script src='{% static "$new_module_name".js %}'></script>\n{% endblock %}"
    echo "----------------------------"
fi

# a bit more yelling at the user
./manage.py show_urls | grep $module
echo "^^^^^^ Check to see if this/these page works"
