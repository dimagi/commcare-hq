from thread import _local

BOOTSTRAP_2 = 'bootstrap-2'
BOOTSTRAP_3 = 'bootstrap-3'


def get_bootstrap_version():
    bootstrap_version = _local.BOOTSTRAP_VERSION
    if bootstrap_version is None:
        bootstrap_version = BOOTSTRAP_2
    return bootstrap_version


def set_bootstrap_version3():
    _local.BOOTSTRAP_VERSION = BOOTSTRAP_3


def set_bootstrap_version2():
    _local.BOOTSTRAP_VERSION = BOOTSTRAP_2
