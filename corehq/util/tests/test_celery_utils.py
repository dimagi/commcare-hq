from datetime import datetime, time

from celery.concurrency.base import BasePool
from django.test import SimpleTestCase, override_settings
import mock

from corehq.util.celery_utils import LoadBasedAutoscaler, OffPeakLoadBasedAutoscaler


class Object(object):
    pass


class MockPool(BasePool):
    shrink_raises_exception = False
    shrink_raises_ValueError = False

    def __init__(self, *args, **kwargs):
        super(MockPool, self).__init__(*args, **kwargs)
        self._pool = Object()
        self._pool._processes = self.limit

    def grow(self, n=1):
        self._pool._processes += n

    def shrink(self, n=1):
        if self.shrink_raises_exception:
            raise KeyError('foo')
        if self.shrink_raises_ValueError:
            raise ValueError('foo')
        self._pool._processes -= n

    @property
    def num_processes(self):
        return self._pool._processes


class BaseTestLoadScaler(SimpleTestCase):
    scaler_class = None

    def assert_scale_up(self, current_procs, new_procs=None, max_procs=4):
        new_procs = new_procs or current_procs + 1
        pool = MockPool(current_procs)
        worker = mock.Mock(name='worker')
        self.assertEqual(pool.num_processes, current_procs)
        x = self.scaler_class(pool, max_procs, 0, worker=worker, keepalive=0.1)
        x._last_action = 0.1
        self.assertTrue(x._maybe_scale())
        self.assertEqual(pool.num_processes, new_procs)

    def assert_scale_down(self, current_procs, new_procs=None, max_procs=4):
        new_procs = new_procs or current_procs - 1
        pool = MockPool(current_procs)
        worker = mock.Mock(name='worker')
        self.assertEqual(pool.num_processes, current_procs)
        x = self.scaler_class(pool, max_procs, 0, worker=worker, keepalive=0.1)
        x._last_action = 0.1
        self.assertTrue(x._maybe_scale())
        self.assertEqual(pool.num_processes, new_procs)

    def assert_no_scale(self, current_procs, max_procs=4):
        pool = MockPool(current_procs)
        worker = mock.Mock(name='worker')
        self.assertEqual(pool.num_processes, current_procs)
        x = self.scaler_class(pool, max_procs, 0, worker=worker, keepalive=0.1)
        x._last_action = 0.1
        self.assertFalse(x._maybe_scale())
        self.assertEqual(pool.num_processes, current_procs)


class TestLoadBasedScaler(BaseTestLoadScaler):
    scaler_class = LoadBasedAutoscaler

    @mock.patch('corehq.util.celery_utils.LoadBasedAutoscaler.qty', 6)
    def test_fewer_processes_than_tasks(self):
        self.assert_scale_up(0, 4)

    @mock.patch('corehq.util.celery_utils.LoadBasedAutoscaler.qty', 6)
    def test_pool_equals_autoscale_max(self):
        self.assert_no_scale(4, 4)

    @mock.patch('corehq.util.celery_utils.LoadBasedAutoscaler.qty', 1)
    def test_more_processes_than_tasks(self):
        self.assert_scale_down(4, 1)

    @mock.patch('corehq.util.celery_utils.LoadBasedAutoscaler.qty', 6)
    @mock.patch('corehq.util.celery_utils.os.getloadavg')
    @mock.patch('corehq.util.celery_utils.multiprocessing.cpu_count')
    def test_fewer_processes_than_task_high_load(self, cpu_count, load_avg):
        load_avg.return_value = [2, 2, 2]
        cpu_count.return_value = 1
        self.assert_scale_down(2)


class TestOffPeakLoadBasedScaler(BaseTestLoadScaler):
    scaler_class = OffPeakLoadBasedAutoscaler

    @override_settings(OFF_PEAK_TIME=(time(0), time(12)))
    @mock.patch('corehq.util.celery_utils.LoadBasedAutoscaler.qty', 6)
    @mock.patch('corehq.util.celery_utils.datetime')
    def test_fewer_processes_than_tasks_during_peak(self, mock_now):
        # Shouldn't scale up during peak times
        mock_now.utcnow = mock.Mock(return_value=datetime(2017, 7, 12, 13, 0, 0, 0))
        self.assert_no_scale(0)

    @override_settings(OFF_PEAK_TIME=(time(0), time(12)))
    @mock.patch('corehq.util.celery_utils.LoadBasedAutoscaler.qty', 6)
    @mock.patch('corehq.util.celery_utils.datetime')
    def test_fewer_processes_than_tasks_off_peak(self, mock_now):
        # Should scale up during off peak times
        mock_now.utcnow = mock.Mock(return_value=datetime(2017, 7, 12, 1, 0, 0, 0))
        self.assert_scale_up(0, 4)
