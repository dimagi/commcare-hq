git checkout master &&
git pull origin master &&
git submodule update --init --recursive &&
pip install --upgrade pip &&
pip install -r requirements/dev-requirements.txt &&
find . -name '*.pyc' -delete &&
./manage.py sync_couch_views &&
./manage.py migrate &&
yarn install --frozen-lockfile
