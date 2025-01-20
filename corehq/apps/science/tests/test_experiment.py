import gc
from contextlib import contextmanager
from time import sleep
from unittest.mock import patch

import pytest
from unmagic import fixture

from corehq.util.metrics.tests.utils import capture_metrics
from corehq.util.test_utils import capture_log_output

from .. import experiment

experiment_ = experiment(
    campaign='test',
    path='module.path',
    old_args={'x': 2},
    new_args={'x': 4},
)


def test_experiment():
    @experiment_
    def func(a, *, x):
        return a + x

    with capture_log_output("notify") as log:
        assert func(1) == 3
    assert log.get_output() == "func(1): 3 != 5\n"


def test_experiment_timing_metrics():
    def sleeper(seconds):
        sleep(seconds)

    sleep2 = experiment_(
        sleeper,
        old_args={"seconds": .0011},
        new_args={"seconds": .002},
    )
    with capture_metrics() as metrics, gc_disabled():
        sleep2()
    assert metrics.to_flattened_dict() == {
        'commcare.science.time.campaign:test': 1,
        'commcare.science.time.path:module.path.sleeper': 1,
        'commcare.science.time.duration:lt_0.01s': 1,
        'commcare.science.diff.campaign:test': 1,
        'commcare.science.diff.path:module.path.sleeper': 1,
        'commcare.science.diff.percent:lt_200%': 1,
    }


def test_experiment_negative_timing_metrics():
    def sleeper(seconds):
        sleep(seconds)

    sleep2 = experiment_(
        sleeper,
        old_args={"seconds": .002},
        new_args={"seconds": .0001},
    )
    with capture_metrics() as metrics, gc_disabled():
        sleep2()
    mets = metrics.to_flattened_dict()
    assert mets.get('commcare.science.diff.percent:lt_050%') == 1


def test_experiment_with_old_error():
    @experiment_
    def fail(x):
        if x == 2:
            raise ValueError("bad value")
        return x

    with (
        capture_log_output("notify") as log,
        pytest.raises(ValueError, match="bad value"),
    ):
        fail()
    assert log.get_output() == "fail(): raised ValueError('bad value') != 4\n"


def test_experiment_with_new_error():
    @experiment_
    def fail(x):
        if x == 4:
            raise ValueError("bad value")
        return 42

    with capture_metrics() as metrics, capture_log_output("notify") as log:
        assert fail() == 42
    mets = metrics.to_flattened_dict()
    logs = log.get_output()
    assert mets.get('commcare.science.diff.path:module.path.fail') == 1
    assert "new code path failed in experiment\n" in logs
    assert logs.endswith("ValueError: bad value\n")


def test_experiment_with_matching_errors():
    @experiment_
    def fail(x):
        raise ValueError("bad value")

    with (
        capture_log_output("notify") as log,
        pytest.raises(ValueError, match="bad value"),
    ):
        fail()
    assert log.get_output() == ""


def test_experiment_with_mismatched_errors():
    @experiment_
    def fail(x):
        raise ValueError("bad" if x == 2 else "worse")

    with (
        capture_log_output("notify") as log,
        pytest.raises(ValueError, match="bad"),
    ):
        fail()
    assert log.get_output() == \
        "fail(): raised ValueError('bad') != raised ValueError('worse')\n"


def test_experiment_with_long_arg():
    @experiment_
    def func(a, *, x):
        return x

    with capture_log_output("notify") as log:
        assert func("ha" * 100) == 2
    haha = repr("ha" * 40)[:80] + "..."
    assert log.get_output() == f"func({haha}): 2 != 4\n"


@fixture(scope="module", autouse=__file__)
def enable_all_experiments():
    with (
        patch("corehq.apps.science.models.is_enabled", return_value=True),
        patch("corehq.apps.science.models.should_record_metrics", return_value=True),
    ):
        yield


@contextmanager
def gc_disabled():
    enabled = gc.isenabled()
    if enabled:
        gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()
