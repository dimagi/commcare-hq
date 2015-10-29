#!/bin/bash
set -ev

if [ "${MATRIX_TYPE}" = "python" ]; then
    pip install coverage unittest2 mock --use-mirrors
elif [ "${MATRIX_TYPE}" = "javascript" ]; then
    npm install -g bower
    npm install -g grunt
    npm install -g grunt-cli
    ln -nfs `which bower` /home/travis/bower
    python manage.py bower install
    npm install
fi
