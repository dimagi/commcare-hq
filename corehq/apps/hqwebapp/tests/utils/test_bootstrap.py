from testil import eq

from corehq.apps.hqwebapp.utils.bootstrap import (
    get_bootstrap_version,
    set_bootstrap_version5,
    set_bootstrap_version3,
    BOOTSTRAP_3,
    BOOTSTRAP_5,
)


def test_default_bootstrap_version():
    eq(get_bootstrap_version(), BOOTSTRAP_3)


def test_set_bootstrap_version5():
    set_bootstrap_version5()
    eq(get_bootstrap_version(), BOOTSTRAP_5)


def test_set_bootstrap_version3():
    set_bootstrap_version5()
    set_bootstrap_version3()
    eq(get_bootstrap_version(), BOOTSTRAP_3)
