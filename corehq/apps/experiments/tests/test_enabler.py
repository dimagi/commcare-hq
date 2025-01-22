import random
import time
from unittest.mock import patch

from django.test import TestCase

import pytest
from unmagic import fixture

from corehq.util.metrics.tests.utils import capture_metrics
from corehq.util.test_utils import capture_log_output

from .. import Experiment
from ..models import ExperimentEnabler, _get_enablers, is_enabled, should_record_metrics

PARENT_PATH = Experiment.__module__.rsplit(".", 1)[0]
FUNC_PATH = f"{__name__}.make_func.<locals>.func"


def enabled(percent, path=FUNC_PATH, campaign='test'):
    @fixture
    def enable():
        ExperimentEnabler.objects.create(
            campaign=campaign,
            path=path,
            enabled_percent=percent,
        )
        _get_enablers.clear(campaign)
        yield
        _get_enablers.clear(campaign)
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


@fixture
def temporary_random_seed():
    state = random.getstate()
    random.seed(0)
    yield
    random.setstate(state)


@temporary_random_seed
class TestIsEnabled(TestCase):

    @enabled(0)
    def test_0_percent(self):
        num = sum(is_enabled('test', FUNC_PATH) for x in range(300))
        assert num == 0

    @enabled(1)
    def test_1_percent(self):
        num = sum(is_enabled('test', FUNC_PATH) for x in range(300))
        assert num == 2

    @enabled(49)
    def test_49_percent(self):
        num = sum(is_enabled('test', FUNC_PATH) for x in range(300))
        assert num == 145

    @enabled(75)
    def test_75_percent(self):
        num = sum(is_enabled('test', FUNC_PATH) for x in range(300))
        assert num == 219

    @enabled(100)
    def test_100_percent(self):
        num = sum(is_enabled('test', FUNC_PATH) for x in range(300))
        assert num == 300

    @enabled(100)
    def test_caching(self):
        def fn(campaign):
            nonlocal calls
            calls += 1
            return {}

        calls = 0
        with patch.object(_get_enablers.__closure__[0].cell_contents, "fn", fn):
            for x in range(300):
                is_enabled('test', FUNC_PATH)
        assert calls == 1

    @enabled(0, path=PARENT_PATH)
    def test_parent_package_is_disabled(self):
        assert is_enabled('test', FUNC_PATH) is False
        assert should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path') is False
        assert should_record_metrics('test', 'other.path')

    @enabled(100, path=PARENT_PATH)
    def test_parent_package_is_enabled(self):
        assert is_enabled('test', FUNC_PATH)
        assert should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path') is False
        assert should_record_metrics('test', 'other.path')

    @enabled(102, path=PARENT_PATH)
    def test_parent_package_new_only_enabled_should_not_record_metrics(self):
        assert is_enabled('test', FUNC_PATH) is None
        assert not should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path') is False
        assert should_record_metrics('test', 'other.path')

    @enabled(0, path='')
    def test_all_packages_is_disabled(self):
        assert is_enabled('test', FUNC_PATH) is False
        assert should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path') is False
        assert should_record_metrics('test', 'other.path')

    @enabled(100, path='')
    def test_all_packages_enabled(self):
        assert is_enabled('test', FUNC_PATH)
        assert should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path')
        assert should_record_metrics('test', 'other.path')

    @enabled(102, path='')
    def test_all_packages_new_only_enabled_should_not_record_metrics(self):
        assert is_enabled('test', FUNC_PATH) is None
        assert not should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path') is None
        assert not should_record_metrics('test', 'other.path')

    @enabled(-1, path='')
    @enabled(100, path=__name__)
    def test_specific_path_wins(self):
        assert is_enabled('test', FUNC_PATH)
        assert should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path') is False
        assert not should_record_metrics('test', 'other.path')

    @enabled(100, campaign='other')
    def test_other_campaign(self):
        assert is_enabled('test', FUNC_PATH) is False
        assert should_record_metrics('test', FUNC_PATH)
        assert is_enabled('test', 'other.path') is False
        assert should_record_metrics('test', 'other.path')


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
    assert func.experiment.path == FUNC_PATH
    return func, calls
