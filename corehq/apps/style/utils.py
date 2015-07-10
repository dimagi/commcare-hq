import threading

_thread_local = threading.local()

BOOTSTRAP_2 = 'bootstrap-2'
BOOTSTRAP_3 = 'bootstrap-3'


def get_bootstrap_version():
    try:
        bootstrap_version = _thread_local.BOOTSTRAP_VERSION
    except AttributeError:
        bootstrap_version = BOOTSTRAP_2
    return bootstrap_version


def set_bootstrap_version3():
    _thread_local.BOOTSTRAP_VERSION = BOOTSTRAP_3


def set_bootstrap_version2():
    _thread_local.BOOTSTRAP_VERSION = BOOTSTRAP_2
