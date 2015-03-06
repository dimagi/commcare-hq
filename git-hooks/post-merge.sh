#!/bin/sh

# Notify if requirements files are changed
CHANGED=`git diff HEAD@{1} --stat -- $GIT_DIR/../requirements/ | wc -l`
if [ $CHANGED -gt 0 ];
then
    echo "Requirements files changed"
    git diff HEAD@{1} -- ./requirements/
    echo "You might want to update your environment as per above requirements changes"
fi
