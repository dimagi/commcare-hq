import threading

_thread_local = threading.local()

BOOTSTRAP_3 = 'bootstrap3'
BOOTSTRAP_5 = 'bootstrap5'


def get_bootstrap_version():
    try:
        bootstrap_version = _thread_local.BOOTSTRAP_VERSION
    except AttributeError:
        bootstrap_version = BOOTSTRAP_3
    return bootstrap_version


def set_bootstrap_version3():
    _thread_local.BOOTSTRAP_VERSION = BOOTSTRAP_3


def set_bootstrap_version5():
    _thread_local.BOOTSTRAP_VERSION = BOOTSTRAP_5
