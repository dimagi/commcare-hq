function staticfiles-hammer() {
    ./manage.py collectstatic --noinput &&
    ./manage.py compilejsi18n &&
    ./manage.py fix_less_imports_collectstatic &&
    ./manage.py compress
}
