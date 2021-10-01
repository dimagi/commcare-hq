rm -rf staticfiles/ &&
./manage.py resource_static &&
./manage.py collectstatic --noinput &&
./manage.py compilejsi18n &&
./manage.py build_requirejs
