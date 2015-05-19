#!/bin/bash

# Make an alias to start this project
# alias hq="cd ~/commcare-hq/ && workon hq-env && source ~/commcare-hq/scripts/utils.sh

export PYTHONPATH=$PYTHONPATH:$DJANGO_PROJECT_ROOT
alias cdpackages="cd $VIRTUAL_ENV/local/lib/python2.7/site-packages/"
alias dj="$DJANGO_PROJECT_ROOT/manage.py"
alias djgun="$DJANGO_PROJECT_ROOT/manage.py run_gunicorn -c services/gunicorn_conf.py -k gevent"
alias djrun="$DJANGO_PROJECT_ROOT/manage.py runserver" # --werkzeug
alias url="$DJANGO_PROJECT_ROOT/manage.py show_urls | grep "

function pyc-purge() {
    find . -name '*.pyc' -delete
}

# Pull latest master of all submodules.  Use this to update them before a deploy
function pull-latest-masters() {
    git checkout master
    git pull origin master
    git submodule update --init
    git submodule foreach --recursive 'git checkout master; git pull origin master &'
    until [ -z "$(ps aux | grep '[g]it pull')" ]; do sleep 1; done
    pyc-purge
}

# Get on the latest master
function update-code() {
    git checkout master
    git pull origin master
    git submodule update --init --recursive
    pyc-purge
}

# Run a devserver which autorestarts on hard failure (ctrl+c twice to quit)
function djrunserver() {
    while true; do
        echo "Starting Django dev server"
        $DJANGO_PROJECT_ROOT/manage.py runserver # --werkzeug
        sleep 1
    done
}

function show-branches() {
    for BRANCH in `git branch | grep -v '\\*'`
    do
        echo $(git log $BRANCH -1\
        --pretty="
            %C(magenta)%ad
            %C(reset)<name>
            %C(yellow)%s
            %C(red)%d
            %C(reset)
        ") | sed "s/<name>/$BRANCH -/g"
    done
}

function delete-merged() {
    if [ $(branch) = 'master' ]
        then git branch --merged master | grep -v '\*' | xargs -n1 git branch -d
        else echo "You are not on branch master"
    fi
}

# Try everything to make this work
function hammer() {
    git checkout master
    git pull origin master
    git submodule update --init --recursive
    pip install -r requirements/requirements.txt -r requirements/dev-requirements.txt -r requirements/prod-requirements.txt
    find . -name '*.pyc' -delete
    $DJANGO_PROJECT_ROOT/manage.py syncdb --migrate
}

