function hammer() {
    git checkout master &&
    git pull origin master &&
    git submodule update --init --recursive &&
    pip install -r requirements/dev-requirements.txt &&
    find . -name '*.pyc' -delete &&
    ./manage.py migrate &&
    bower install
}
