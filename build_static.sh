#!/usr/bin/env bash

# version static
python manage.py resource_static --skip-cache

# bower install
bower prune --production --config.interactive=false
bower install --production --config.interactive=false
bower update --production --config.interactive=false

# npm install
npm prune --production
npm install --production
npm update --production

# collectstatic
python manage.py collectstatic --noinput -v 0
python manage.py fix_less_imports_collectstatic
python manage.py compilejsi18n

# compress
python manage.py compress --force -v 0
python manage.py purge_compressed_files

# update translations
python manage.py update_django_locales
python manage.py compilemessages -v 0

mkdir -p build/staticfiles

cp -r staticfiles/* build/staticfiles
