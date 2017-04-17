#!/bin/bash

# This lets you get notified, when files that affect your dev environment
# changes, caused when merging new code into your worktree
# To use this, copy this script to your ./git/hooks/post-merge file

# Settings to enable notifications for specific files
# Notify if any of requirement files change
NOTIFY_REQUIREMENTS=true

# Notify if localsettings.example.py file changes (helpful when a new setting is introduced)
NOTIFY_NEW_LOCALSETTINGS=true

# Notify if requirements files are changed
REQUIREMENTS_CHANGED=`git diff HEAD@{1} --stat -- $GIT_DIR/../requirements/ | wc -l`
if [ $NOTIFY_REQUIREMENTS ] && [ $REQUIREMENTS_CHANGED -gt 0 ];
then
    echo "Requirements files changed as per below"
    git diff HEAD@{1} -- ./requirements/
    echo "You might want to update your environment as per above requirements changes"
    echo
fi

# Notify if localsettings.example.py has changed
LOCALSETTINGS_CHANGED=`git diff HEAD@{1} --stat -- $GIT_DIR/../localsettings.example.py | wc -l`
if [ $NOTIFY_NEW_LOCALSETTINGS ] && [ $LOCALSETTINGS_CHANGED -gt 0 ];
then
    echo "Localsettings file changed as per below"
    git diff HEAD@{1} -- ./localsettings.example.py
    echo "You might want to update your environment as per above localsettings changes]"
fi
