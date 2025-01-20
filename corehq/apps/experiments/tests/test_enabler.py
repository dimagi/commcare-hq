import time

from django.test import TestCase

import pytest
from unmagic import fixture

from corehq.util.metrics.tests.utils import capture_metrics
from corehq.util.test_utils import capture_log_output

from .. import Experiment
from ..models import ExperimentEnabler

FUNC_PATH = f"{__name__}.make_func.<locals>.func"


def enabled(percent, path=FUNC_PATH, campaign='test'):
    @fixture
    def enable():
        ExperimentEnabler.objects.create(
            campaign=campaign,
            path=path,
            enabled_percent=percent,
        )
        yield
    return enable


class TestExperimentEnabled(TestCase):

    @enabled(-1)
    def test_disabled_experiment_with_metrics_disabled(self):
        func, calls = make_func()
        with capture_metrics() as metrics, capture_log_output("notify") as log:
            assert func(1) == 3
        assert metrics.to_flattened_dict() == {}
        assert log.get_output() == ""
        assert calls == [(1, 2)]

    @enabled(-1)
    def test_error_in_disabled_experiment_with_metrics_disabled(self):
        func, calls = make_func(ValueError)
        with (
            capture_metrics() as metrics,
            capture_log_output("notify") as log,
            pytest.raises(ValueError),
        ):
            func(1)
        assert metrics.to_flattened_dict() == {}
        assert log.get_output() == ""
        assert calls == [(1, 2)]

    @enabled(0)
    def test_disabled_experiment(self):
        func, calls = make_func()
        with capture_metrics() as metrics, capture_log_output("notify") as log:
            assert func(1) == 3
        assert metrics.to_flattened_dict() == {
            'commcare.experiment.time.campaign:test': 1,
            f'commcare.experiment.time.path:{FUNC_PATH}': 1,
            'commcare.experiment.time.duration:lt_0.01s': 1,
        }
        assert log.get_output() == ""
        assert calls == [(1, 2)]

    @enabled(0)
    def test_error_in_disabled_experiment(self):
        func, calls = make_func(ValueError)
        with (
            capture_metrics() as metrics,
            capture_log_output("notify") as log,
            pytest.raises(ValueError),
        ):
            func(1)
        assert metrics.to_flattened_dict() == {
            'commcare.experiment.time.campaign:test': 1,
            f'commcare.experiment.time.path:{FUNC_PATH}': 1,
            'commcare.experiment.time.duration:lt_0.01s': 1,
        }
        assert log.get_output() == ""
        assert calls == [(1, 2)]

    @enabled(100)
    def test_experiment_run_old_and_new(self):
        func, calls = make_func()
        with capture_metrics() as metrics, capture_log_output("notify") as log:
            assert func(1) == 3
        assert metrics.to_flattened_dict() == {
            'commcare.experiment.time.campaign:test': 1,
            f'commcare.experiment.time.path:{FUNC_PATH}': 1,
            'commcare.experiment.time.duration:lt_0.01s': 1,
            'commcare.experiment.diff.campaign:test': 1,
            f'commcare.experiment.diff.path:{FUNC_PATH}': 1,
            'commcare.experiment.diff.duration:lt_200%': 1,
        }
        assert log.get_output() == "func(1): 3 != 5\n"
        assert calls == [(1, 2), (1, 4)]

    @enabled(100)
    def test_error_in_experiment_run_old_and_new(self):
        func, calls = make_func(ValueError)
        with (
            capture_metrics() as metrics,
            capture_log_output("notify") as log,
            pytest.raises(ValueError),
        ):
            func(1)
        assert metrics.to_flattened_dict() == {
            'commcare.experiment.time.campaign:test': 1,
            f'commcare.experiment.time.path:{FUNC_PATH}': 1,
            'commcare.experiment.time.duration:lt_0.01s': 1,
            'commcare.experiment.diff.campaign:test': 1,
            f'commcare.experiment.diff.path:{FUNC_PATH}': 1,
            'commcare.experiment.diff.duration:lt_200%': 1,
        }
        assert log.get_output() == ""
        assert calls == [(1, 2), (1, 4)]

    @enabled(101)
    def test_disabled_experiment_run_only_new(self):
        func, calls = make_func()
        with capture_metrics() as metrics, capture_log_output("notify") as log:
            assert func(1) == 5
        assert metrics.to_flattened_dict() == {
            'commcare.experiment.time.campaign:test': 1,
            f'commcare.experiment.time.path:{FUNC_PATH}': 1,
            'commcare.experiment.time.duration:lt_0.01s': 1,
        }
        assert log.get_output() == ""
        assert calls == [(1, 4)]

    @enabled(101)
    def test_error_in_disabled_experiment_run_only_new(self):
        func, calls = make_func(ValueError)
        with (
            capture_metrics() as metrics,
            capture_log_output("notify") as log,
            pytest.raises(ValueError),
        ):
            func(1)
        assert metrics.to_flattened_dict() == {
            'commcare.experiment.time.campaign:test': 1,
            f'commcare.experiment.time.path:{FUNC_PATH}': 1,
            'commcare.experiment.time.duration:lt_0.01s': 1,
        }
        assert log.get_output() == ""
        assert calls == [(1, 4)]

    @enabled(102)
    def test_enabled_experiment_with_metrics_disabled(self):
        func, calls = make_func()
        with capture_metrics() as metrics, capture_log_output("notify") as log:
            assert func(1) == 5
        assert metrics.to_flattened_dict() == {}
        assert log.get_output() == ""
        assert calls == [(1, 4)]

    @enabled(102)
    def test_error_in_new_only_experiment_with_metrics_disabled(self):
        func, calls = make_func(ValueError)
        with (
            capture_metrics() as metrics,
            capture_log_output("notify") as log,
            pytest.raises(ValueError),
        ):
            func(1)
        assert metrics.to_flattened_dict() == {}
        assert log.get_output() == ""
        assert calls == [(1, 4)]


def make_func(error=None):
    @Experiment(
        campaign='test',
        old_args={'x': 2},
        new_args={'x': 4},
    )
    def func(a, *, x):
        calls.append((a, x))
        # sleep for deterministic diff % metrics
        time.sleep(0.001 * (1 if x == 2 else 1.5))
        if error is not None:
            raise error
        return a + x

    calls = []
    return func, calls
