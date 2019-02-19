function build-requirejs() {
    rm -rf staticfiles/ &&
    ./manage.py collectstatic --noinput &&
    ./manage.py compilejsi18n &&
    ./manage.py build_requirejs
}
