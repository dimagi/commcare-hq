git checkout master &&
git pull origin master &&
git submodule update --init --recursive &&
uv sync --compile-bytecode &&
( [ -f requirements/local.txt ] && uv pip install -r requirements/local.txt || true ) &&
find . -name '*.pyc' -not -path './.venv/*' -delete &&
./manage.py sync_couch_views &&
./manage.py migrate &&
yarn install --frozen-lockfile
