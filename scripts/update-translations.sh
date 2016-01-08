#!/bin/bash

# Based on this confluence page:
# https://confluence.dimagi.com/display/commcarehq/Internationalization+and+Localization+-+Transifex+Translations

function abort () {
    echo $1
    echo "Aborting."
    exit 1
}

has_local_changes=`git diff-index HEAD` && true
if [[ $has_local_changes ]]
then
    abort "You have uncommitted changes in your working tree."
fi

branch=$(git rev-parse --abbrev-ref HEAD)
if [[ $branch != 'master' ]]
then
    abort "You must be on master to run this command."
fi

if [[ ! `command -v tx` || ! -f ~/.transifexrc ]]
then
    echo "It looks like you haven't yet configured transifex."
    echo "Please visit the wiki page for instructions on how to do so:"
    echo "https://confluence.dimagi.com/display/commcarehq/Internationalization+and+Localization+-+Transifex+Translations"
fi

echo "Pulling translations from transifex"
tx pull -f

echo "Gathering all translation strings.  Note that this will probably take a while"
./manage.py makemessages --all
echo "Gathering javascript translation strings.  This will also probably take a while"
./manage.py makemessages -d djangojs --all
echo "Compiling translation files."
./manage.py compilemessages

echo "Pushing updates to transifex."
tx push -st

has_local_changes=`git diff-index HEAD` && true
if [[ ! $has_local_changes ]]
then
    abort "There are no changes....please investigate"
fi

echo "Committing and pushing changes"
git add locale/
git commit --edit --message="Update translations." --message="[ci skip]"
git push origin master
