#!/bin/bash
set -euo pipefail  # bash strict mode - exit on hard failures

# Based on this confluence page:
# https://confluence.dimagi.com/display/commcarehq/Internationalization+and+Localization+-+Transifex+Translations

function abort () {
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

echo "Gathering all translation strings.  Note that this will probably take a while"
./manage.py makemessages --all --ignore 'corehq/apps/app_manager/tests/data/v2_diffs*' --ignore 'node_modules'

echo "Gathering javascript translation strings.  This will also probably take a while"
./manage.py makemessages -d djangojs --all

set +e   # Temporarily disable strict mode so we can respond any failure
echo "Compiling translation files."
./manage.py compilemessages
if [[ $? -ne "0" ]]; then
    echo ""
    echo "'./manage.py compilemessages' failed.  This is probably due to a bad translation, maybe a translator messed up a format string or something."
    echo "If the deploy is urgent, it might be best to drop the changes to locale/ and deploy without updating translations, then assign an interrupt ticket to fix."
    echo "The output above from compilemessages should have specifics about the locale/ file and line where the error(s) occurred."
    echo "1. Open those files, go to the appropriate lines and fix the errors."
    echo "2. Run './manage.py compilemessages' again to make sure it's fixed."
    echo "3. Run 'tx push -st' to update them on transifex."
    echo "4. Now if you do 'git checkout -- locale' and run this script again, it should succeed."
    echo "5. You should probably also reach out to the translator to make sure they don't mess this up again."
    abort
fi
set -e

echo "Pushing updates to transifex."
tx push -st

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
