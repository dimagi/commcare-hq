if [ $MATRIX_TYPE == "python" ]; then
    coverage run manage.py test --noinput --failfast --traceback --verbosity=2 --testrunner=$TESTRUNNER
elif [ $MATRIX_TYPE == "javascript" ]; then
    python manage.py migrate --noinput
    python manage.py runserver 8000 &  # Used to run mocha browser tests
    mocha grunt
fi
