"""Enforce a maximum time for various test events, fail if the limit is exceeded
"""
import os
import time
import warnings

import pytest
from unmagic.scope import get_active


def pytest_addoption(parser):
    parser.addoption(
        '--max-test-time', type=float, dest="max_test_time",
        default=get_float(os.environ.get('CCHQ_MAX_TEST_TIME'), 0),
        help='Fail test if it runs for longer than this limit (seconds). '
             'Use `corehq.tests.util.timelimit.timelimit` to '
             'override the time limit for individual tests or '
             'functions called by tests.'
    )


def pytest_configure(config):
    config.max_test_time = config.getoption("--max-test-time")
    if config.max_test_time:
        config.pluginmanager.register(MaxTestTimePlugin(), "timelimit")


class MaxTestTimePlugin:

    def __init__(self):
        self.limits = None
        self.time = time.time  # evade freezegun

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_setup(self, item):
        yield from self.enforce_limit(item, "setup")

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item):
        yield from self.enforce_limit(item, "test")

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_teardown(self, item):
        yield from self.enforce_limit(item, "teardown")

    def enforce_limit(self, item, event):
        limits = self.limits = []
        start = self.time()
        yield
        duration = self.time() - start
        limit = max(sum(limits), item.config.max_test_time)
        if duration > limit:
            raise AssertionError(f"{event} time limit ({limit}) exceeded: {duration}")
        self.limits = None


def get_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def increase_max_test_time(value):
    """Increase the maximum amount of time allowed for the active test phase

    If it is greater, the sum of values passed to this function will be
    used instead of --max-test-time.
    """
    try:
        plugin = get_active().session.config.pluginmanager.get_plugin("timelimit")
    except (ValueError, AttributeError):
        warnings.warn("timelimit used outside of test?")
        return
    if plugin is not None:
        if plugin.limits is None:
            warnings.warn("timelimit used outside of runtest lifecycle")
        else:
            plugin.limits.append(value)


def get_max_test_time(obj):
    return getattr(obj, "max_test_time", 0)
