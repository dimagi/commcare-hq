#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import importlib


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
    except AttributeError:
        from dimagi.utils.logging import notify_exception
        notify_exception(
            None,
            message="AttributeError in to_function", details=module.__dict__,
        )
        if failhard:
            raise
    except ImportError:
        if failhard:
            raise
