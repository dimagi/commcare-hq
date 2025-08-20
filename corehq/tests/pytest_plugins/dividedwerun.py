import os
from hashlib import md5
from unittest import TestCase

import pytest
from django.test import SimpleTestCase


def pytest_addoption(parser):
    parser.addoption('--divided-we-run',
                     default=os.environ.get('DIVIDED_WE_RUN'),
                     help="Run a predictably random subset of tests based "
                          "on test name. The value of this option should "
                          "be one or two hexadecimal digits denoting the "
                          "first and last bucket to include, where each "
                          "bucket is a predictably random hex digit based "
                          "on the fully qualified test name. "
                          "[DIVIDED_WE_RUN]")


def pytest_configure(config):
    config.reuse_db = reusedb = config.getoption("--reusedb")
    config.skip_setup_for_reuse_db = reusedb and reusedb != "reset"
    test_range = config.getoption("--divided-we-run")
    if test_range:
        if len(test_range) not in [1, 2]:
            raise ValueError("invalid divided-we-run value: "
                             "expected 1 or 2 hexadecimal digits")
        config.divided_we_run = test_range
        first, last = test_range[0], test_range[-1]
        if int(first, 16) > int(last, 16):
            raise ValueError("divided-we-run range start is after range end")
        config.divided_we_run_range = first, last


def pytest_collection_modifyitems(config, items):
    if not hasattr(config, "divided_we_run"):
        return
    rng = config.divided_we_run
    skip = {bucket: pytest.mark.skip(
        reason=f"divided-we-run: {bucket!r} not in range {rng!r}"
    ) for bucket in "0123456789abcdef"}
    first, last = config.divided_we_run_range
    for item in items:
        bucket = get_score(item)
        if bucket < first or bucket > last:
            item.add_marker(skip[bucket])


def name_of(test):
    if hasattr(test.module, "setup_module"):
        # group all tests with module-level setup
        return test.module.__name__
    if hasattr(test.cls, 'setUpClass'):
        # group all tests with non-simple setUpClass
        setupclass = get_setupclass(test.cls)
        if not (
            setupclass is get_setupclass(TestCase)
            or setupclass is get_setupclass(SimpleTestCase)
        ):
            return "::".join([test.module.__name__, test.cls.__name__])
    return test.nodeid


def get_setupclass(cls):
    return cls.setUpClass.__func__


def get_score(test):
    """Returns the score for a test, which is derived from the MD5 hex digest
    of the test's (possibly truncated) name.

    Calls ``name_of(test)`` to acquire the "full name", then truncates that
    value at the first occurrence of an open-parenthesis character (or the
    entire name if none exist) before generating the MD5 digest.

    Example:

    .. code-block:: python

        >>> name_of(test_this)
        'module.test_func[<This at 0xffffaaaaaaaa>]'
        >>> name_of(test_that)
        'module.test_func[<Other at 0xffffeeeeeeee>]'
        >>> md5(name_of(test_this)).hexdigest()
        '45fd9a647841b1e65633f332ee5f759b'
        >>> md5(name_of(test_that)).hexdigest()
        'acf7e690fb7d940bfefec1d06392ee17'
        >>> get_score(test_this)
        'c'
        >>> get_score(test_that)
        'c'
    """
    runtime_safe = name_of(test).split("[", 1)[0]
    return md5(runtime_safe.encode('utf-8')).hexdigest()[0]
