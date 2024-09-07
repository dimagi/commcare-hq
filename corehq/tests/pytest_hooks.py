import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests():
    assert not hasattr(pytest_load_initial_conftests, 'loaded'), "Already loaded"
    pytest_load_initial_conftests.loaded = True
    os.environ.setdefault('CCHQ_TESTING', '1')

    from manage import init_hq_python_path, run_patches
    init_hq_python_path()
    run_patches()

    from corehq.warnings import configure_warnings
    configure_warnings(is_testing=True)

    from .nosecompat import create_nose_virtual_package
    create_nose_virtual_package()


def pytest_pycollect_makeitem(collector, name, obj):
    """Fail on common mistake that results in masked tests"""
    if (
        "Test" in name
        and not isinstance(obj, type)
        and isinstance(wrapped := _get_wrapped(obj), type)
        and any(n.startswith("test_") for n in dir(wrapped))
    ):
        return pytest.fail(
            f"{obj.__module__}.{name} appears to be a test class that has "
            "been wrapped with a decorator that masks its tests."
        )
    return None


def _get_wrapped(obj):
    while hasattr(obj, "__wrapped__"):
        obj = obj.__wrapped__
    return obj
