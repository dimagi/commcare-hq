#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import importlib
import sys


def to_function(function_path, failhard=False):
    """
    Convert a string like foo.bar.baz into a function (assumes that
    baz is a function defined in foo/bar.py).
    """
    try:
        # TODO: make this less brittle if imports or args don't line up
        module, func = function_path.rsplit(".", 1)
        module = importlib.import_module(module)
        actual_func = getattr(module, func)
        return actual_func
    except ImportError:
        if failhard:
            raise

    
def try_import(module_name):
    """
    Import and return *module_name*.

    >>> try_import("csv") # doctest: +ELLIPSIS
    <module 'csv' from '...'>

    Unlike the standard try/except approach to optional imports, inspect
    the stack to avoid catching ImportErrors raised from **within** the
    module. Only return None if *module_name* itself cannot be imported.

    >>> try_import("spam.spam.spam") is None
    True
    """

    try:
        __import__(module_name)
        return sys.modules[module_name]

    except ImportError:

        # extract a backtrace, so we can find out where the exception
        # was raised from. if there is a NEXT frame, it means that the
        # import statement succeeded, but an ImportError was raised from
        # *within* the imported module. we must allow this error to
        # propagate, to avoid silently masking it.
        traceback = sys.exc_info()[2]
        if traceback.tb_next:
            raise

        # else, the exception was raised from this scope. *module_name*
        # couldn't be imported, which is fine, since allowing that is
        # the purpose of this function.
        return None
