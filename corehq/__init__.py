# This must not import any module that performs app initialization on
# import since it is loaded by manage.py very early during startup as
# a side effect of importing other modules in the package.
#
# Startup logic should be invoked in a Django `AppConfig`, in the
# `main()` method of manage.py, and/or in `corehq.celery` for
# celery processes.
