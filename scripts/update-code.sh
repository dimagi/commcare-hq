function delete-pyc() {
    find . -name '*.pyc' -delete
}
function pull-latest-master() {
    git checkout master &&
    git pull origin master &&
    git submodule update --init &&
    git submodule foreach --recursive 'git checkout master; git pull origin master &'
    until [ -z "$(ps aux | grep '[g]it pull')" ]; do sleep 1; done
}
function update-code() {
    pull-latest-master &&
    delete-pyc
}
