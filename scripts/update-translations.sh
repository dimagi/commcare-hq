#!/bin/bash
set -euo pipefail  # bash strict mode - exit on hard failures

# Based on this confluence page:
# https://dimagi.atlassian.net/wiki/spaces/saas/pages/2146607277/Internationalization+and+Localization+-+Transifex+Translations

function abort () {
    echo $@
    echo "Aborting."
    exit 1
}

function help () {
    echo "Update Translations"
    echo
    echo "Syntax: scripts/update-translations.sh [-h|--no-fuzzy|--no-obsolete]"
    echo "options:"
    echo " --no-fuzzy   Remove fuzzy translations"
    echo " --no-obsolte Remove obsolete translations"
    echo " -h|--help    Print this help"
    echo
}

while getopts ":h-:" option; do
    if [ "$option" = "-" ]; then
        option="${OPTARG%%=*}"
    fi

    case $option in
        h | help )
            help
            exit;;
    esac
done

if [ -z "${UPDATE_TRANSLATIONS_SKIP_GIT-}" ]
then
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

    git fetch
    tracking_branch=`git rev-parse --abbrev-ref --symbolic-full-name @{u}`
    upstream_changes=`git rev-list HEAD...$tracking_branch --count`
    if [[ $upstream_changes > 0 ]]
    then
        abort "There are changes upstream that you should pull with 'git pull' before running this command."
    fi
fi

if [[ ! `command -v tx` || ! -f ~/.transifexrc ]]
then
    echo "It looks like you haven't yet configured transifex."
    echo "Please visit the wiki page for instructions on how to do so:"
    echo "https://dimagi.atlassian.net/wiki/spaces/saas/pages/2146607277/Internationalization+and+Localization+-+Transifex+Translations"
    abort
fi

# Check if OpenAI client is installed
if ! python -c "import openai" &> /dev/null; then
    echo "OpenAI client is not installed."
    echo "Translations will not be updated with LLM."
    echo "Please install it with: uv pip install openai"
    echo "Then run this script again if you want to update translations with LLM."
    AGENT_INSTALLED=false
else
    AGENT_INSTALLED=true
fi


echo "Pulling translations from transifex"
tx pull

./scripts/make-translations.sh "$@"

if $AGENT_INSTALLED; then
    echo "Updating translations with LLM. Running ./manage.py translate_po_files"
    OPENAI_API_KEY="${OPENAI_API_KEY}" ./manage.py translate_po_files
fi

echo "Pushing updates to transifex."
tx push -s -t

if [ -z "${UPDATE_TRANSLATIONS_SKIP_GIT-}" ]
then
    has_local_changes=`git diff-index HEAD` && true
    if [[ ! $has_local_changes ]]
    then
        abort "There are no changes....please investigate"
    fi

    echo "Committing and pushing changes"
    git add locale/ &&
    git commit --edit --message="Update translations." --message="[ci skip]" &&
    git push origin master
fi

echo "Translations updated successfully!"
