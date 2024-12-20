import os
from pathlib import Path

import pytest
from unmagic import fence

from ddtrace.internal.module import ModuleWatchdog
if ModuleWatchdog.is_installed():
    # Remove ddtrace cruft from tracebacks. ModuleWatchdog is installed
    # unconditionally when ddtrace is imported, which happens early
    # in pytest startup because of ddtrace's pytest11 entry point(s).
    ModuleWatchdog.uninstall()

pytest_plugins = [
    'unmagic',
    'corehq.tests.pytest_plugins.dividedwerun',
    'corehq.tests.pytest_plugins.timelimit',
    'corehq.tests.pytest_plugins.patches',
    'corehq.tests.pytest_plugins.redislocks',
    'corehq.tests.pytest_plugins.reusedb',
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


def pytest_report_teststatus(report, config):
    """Show skipped reason when verbosity >= 2 (-vv)"""
    if report.when in ("setup", "teardown") and report.skipped:
        if config.get_verbosity() >= 2:
            reason = report.longrepr[-1].removeprefix("Skipped: ")
            return "skipped", "s", f"SKIPPED {reason}"
    return None


def _get_wrapped(obj):
    while hasattr(obj, "__wrapped__"):
        obj = obj.__wrapped__
    return obj


def _dirset(path):
    return {p.name for p in path.iterdir() if p.is_dir()}


_ROOT = Path(__file__).parent.parent.parent
fence.install({
    "corehq",
    "couchdbkit_aggregate",
    "django_digest",
    "langcodes",
    "no_exceptions",
    "python_digest",
    "test",
    "testapps",
    "xml2json",
} | _dirset(_ROOT / "custom") | _dirset(_ROOT / "corehq/ex-submodules"))
