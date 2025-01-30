import gc
from contextlib import contextmanager
from time import sleep
from unittest.mock import patch

import pytest
from unmagic import fixture

from corehq.util.metrics.tests.utils import capture_metrics
from corehq.util.test_utils import capture_log_output

from .. import Experiment

experiment = Experiment(
    campaign='test',
    old_args={'x': 2},
    new_args={'x': 4},
)


def test_experiment():
    @experiment
    def func(a, *, x):
        return a + x

    with capture_log_output("notify") as log:
        assert func(1) == 3
    assert log.get_output() == "func(1): 3 != 5\n"

    assert func.experiment.tags == {
        "campaign": "test",
        "path": f"{__name__}.test_experiment.<locals>.func",
    }


def test_method_experiment():
    class Test:
        @experiment
        def func(self, a, *, x):
            return a + x

    with capture_log_output("notify") as log:
        assert Test().func(1) == 3
    assert log.get_output() == "func(<corehq.apps.experim..., 1): 3 != 5\n"

    assert Test.func.experiment.tags == {
        "campaign": "test",
        "path": f"{__name__}.test_method_experiment.<locals>.Test.func",
    }


def test_experiment_timing_metrics():
    def sleeper(seconds):
        sleep(seconds)

    sleep2 = experiment(
        sleeper,
        old_args={"seconds": .0011},
        new_args={"seconds": .002},
    )
    with capture_metrics() as metrics, gc_disabled():
        sleep2()
    assert metrics.to_flattened_dict() == {
        'commcare.experiment.time.campaign:test': 1,
        f'commcare.experiment.time.path:{__name__}.{sleeper.__qualname__}': 1,
        'commcare.experiment.time.enabled:both': 1,
        'commcare.experiment.time.duration:lt_0.01s': 1,
        'commcare.experiment.diff.campaign:test': 1,
        f'commcare.experiment.diff.path:{__name__}.{sleeper.__qualname__}': 1,
        'commcare.experiment.diff.duration:lt_200%': 1,
    }


def test_experiment_negative_timing_metrics():
    def sleeper(seconds):
        sleep(seconds)

    sleep2 = experiment(
        sleeper,
        old_args={"seconds": .002},
        new_args={"seconds": .0001},
    )
    with capture_metrics() as metrics, gc_disabled():
        sleep2()
    mets = metrics.to_flattened_dict()
    assert mets.get('commcare.experiment.diff.duration:lt_050%') == 1


def test_experiment_with_old_error():
    @experiment
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
    @experiment
    def fail(x):
        if x == 4:
            raise ValueError("bad value")
        return 42

    with capture_metrics() as metrics, capture_log_output("notify") as log:
        assert fail() == 42
    mets = metrics.to_flattened_dict()
    logs = log.get_output()
    assert mets.get(f'commcare.experiment.diff.path:{__name__}.{fail.__qualname__}') == 1
    assert "new code path failed in experiment\n" in logs
    assert logs.endswith("ValueError: bad value\n")


def test_experiment_with_matching_errors():
    @experiment
    def fail(x):
        raise ValueError("bad value")

    with (
        capture_log_output("notify") as log,
        pytest.raises(ValueError, match="bad value"),
    ):
        fail()
    assert log.get_output() == ""


def test_experiment_with_mismatched_errors():
    @experiment
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
    @experiment
    def func(a, *, x):
        return x

    with capture_log_output("notify") as log:
        assert func("ha" * 100) == 2
    haha = repr("ha" * 40)[:20] + "..."
    assert log.get_output() == f"func({haha}): 2 != 4\n"


@fixture(scope="module", autouse=__file__)
def enable_all_experiments():
    with (
        patch("corehq.apps.experiments.models.is_enabled", return_value=True),
        patch("corehq.apps.experiments.models.should_record_metrics", return_value=True),
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
