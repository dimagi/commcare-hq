"""Enforce a maximum time for various test events, fail if the limit is exceeded
"""
import os
import time

import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--max-test-time', type=float, dest="max_test_time",
        default=get_float(os.environ.get('CCHQ_MAX_TEST_TIME'), 0),
        help='Fail test if it runs for longer than this limit (seconds). '
             'Use `corehq.util.test_utils.timelimit` to '
             'override the time limit for individual tests.'
    )


def pytest_configure(config):
    config.max_test_time = config.getoption("--max-test-time")
    if config.max_test_time:
        config.pluginmanager.register(MaxTestTimePlugin())


class MaxTestTimePlugin:

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
        limit = get_limit(item)
        if not limit:
            yield
            return
        start = time.time()
        yield
        duration = time.time() - start
        if duration > limit:
            raise AssertionError(f"{event} time limit ({limit}) exceeded: {duration}")


def get_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_limit(item):
    item_limit = get_max_test_time(item.obj) + get_class_limit(item.cls)
    return max(item_limit, item.config.max_test_time)


def get_class_limit(cls):
    return 0 if cls is None else (
        get_max_test_time(getattr(cls, "setUp", None))
        + get_max_test_time(getattr(cls, "tearDown", None))
    )


def get_max_test_time(obj):
    return getattr(obj, "max_test_time", 0)
