NoExceptions
============

Django No Exceptions provides middleware to catch certain exceptions that correspond to HTTP response classes.
It was inspired by Django's Http404, and is used similarly.

Usage
~~~~~~

Setup
------
Add ``'corehq.apps.no_exceptions.middleware.NoExceptionsMiddleware',`` to your ``MIDDLEWARE_CLASSES``.
Optionally set ``LET_HTTP_EXCEPTIONS_500`` (``True``/``False``)
to determine whether to catch NoExceptions exceptions or to pass them through as normal exceptions.
This setting defaults to ``DEBUG``
(pass exceptions through in DEBUG mode, turn them into appropriate responses in production).

Using NoExceptions exceptions
-----------------------------

.. code:: python
    from corehq.apps.no_exceptions import exceptions as x

    def my_view(request, \*args, \**kwargs):
        ...
        if request.is_bad():
            raise x.Http400("You need to foo your bar!")
        ...

Exceptions available are:
| ``Http400`` - CLIENT ERROR
| ``Http401`` - UNAUTHORIZED
| ``Http403`` - FORBIDDEN

Django's own Http404 is also available unchanged in ``no_exceptions.exceptions``

You may also use ``no_exceptions.exceptions.HttpException`` to make your own exceptions on the fly:

.. code:: python
    def my_view(request, \*args, \**kwargs):
        ...
        raise x.HttpException(
                status=418,
                message="I can't help you, I'm a teapot"
        )
        ...

