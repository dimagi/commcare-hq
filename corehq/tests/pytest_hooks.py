import os

import pytest

pytest_plugins = [
    'corehq.tests.pytest_plugins.patches',
    'corehq.tests.pytest_plugins.redislocks',
]


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


def assert_loaded():
    # Not a pytest hook.
    assert getattr(pytest_load_initial_conftests, "loaded", False), """
        pytest requires commcare-hq test hooks. Recommended:

        pip install -e .
    """
