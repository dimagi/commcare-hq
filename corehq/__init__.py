# This must not import any module that performs app initialization on
# import since it is loaded by manage.py very early during startup as
# a side effect of importing other modules in the package.
#
# Startup logic should be invoked in a Django `AppConfig`, in the
# `main()` method of manage.py, and/or in `corehq.celery` for
# celery processes.
import os


def _get_current_app():
    # HACK Celery 4.1 default/current app mechanism is broken when app
    # initilaization is not done as an import side-effect. It either
    # creates a new app when the current app is first requested (which
    # is broken because then tasks get hooked to the wrong app), or
    # (with C_STRICT_APP) it unconditionally raises an error when the
    # current app is accessed. Why is there no way to configure it to
    # raise an error if the current app is accessed before it is set,
    # but not thereafter?
    #
    # Eliminating the thread-local current app hooey should be fine.
    # https://github.com/celery/celery/blob/ab3231dea14501c0159d3caa1fcf83689eb6db2d/celery/app/trace.py#L673-L680
    app = _state.default_app
    if app is None:
        raise RuntimeError("""Celery is not initialized.

        If you are seeing this error it probably means you have imported
        something that depends on the Celery app before initializing it.
        Adjust imports and/or INSTALLED_APPS (see corehq.apps.celery).
        """)
    return app


# Monkey patch Celery. The app will be initialized in
# corehq.apps.celery._init_celery_app during Django setup.
os.environ.setdefault("C_STRICT_APP", "1")
from celery import _state  # noqa: E402
if _state.default_app is not None:
    # Reset default app, which can be initialized by gevent monkey
    # patching, which traverses gc.get_objects() and calls
    # isinstance(...) on each object.
    _state.set_default_app(None)
assert _state._tls.current_app is None, "Current app already created"
assert hasattr(_state.current_app, "_Proxy__local")
object.__setattr__(_state.current_app, "_Proxy__local", _get_current_app)
_state.get_current_app = _get_current_app
