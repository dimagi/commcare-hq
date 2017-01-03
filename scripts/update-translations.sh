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
    abort
fi

echo "Pulling translations from transifex"
tx pull -f

if [[ $? -ne "0" ]]; then
    abort "Pulling from transifex failed."
fi

echo "Gathering all translation strings.  Note that this will probably take a while"
./manage.py makemessages --all --ignore 'corehq/apps/app_manager/tests/data/v2_diffs*' --ignore 'node_modules'

if [[ $? -ne "0" ]]; then
    abort "Looks like there's a problem running makemessages, you should probably fix it."
fi

echo "Gathering javascript translation strings.  This will also probably take a while"
./manage.py makemessages -d djangojs --all

if [[ $? -ne "0" ]]; then
    abort "Looks like there's a problem translating the javascript strings, you should probably fix it."
fi

echo "Compiling translation files."
./manage.py compilemessages

if [[ $? -ne "0" ]]; then
    git checkout -- locale/
    abort "./manage.py compilemessages failed.  This is probably due to a bad translation, maybe a translator messed up a format string or something.  Make an interrupt ticket or something to figure it out."
fi

echo "Pushing updates to transifex."
tx push -st

if [[ $? -ne "0" ]]; then
    abort "Pushing to transifex failed."
fi

has_local_changes=`git diff-index HEAD` && true
if [[ ! $has_local_changes ]]
then
    abort "There are no changes....please investigate"
fi

echo "Committing and pushing changes"
git add locale/ &&
git commit --edit --message="Update translations." --message="[ci skip]" &&
git push origin master

echo "Translations updated successfully!"
