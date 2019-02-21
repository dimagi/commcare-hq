from __future__ import absolute_import
from __future__ import unicode_literals
from unittest import TestCase

from mock import patch, call, ANY

from ..lockmeter import LockMeter


class TestLockMeter(TestCase):

    def test_initially_not_locked(self):
        fake = FakeLock()
        LockMeter(fake, "test")
        self.assertFalse(fake.locked)

    def test_acquire(self):
        fake = FakeLock()
        lock = LockMeter(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as timer:
            lock.acquire()
            self.assertTrue(fake.locked)
        timer.assert_called_once_with("commcare.lock.acquire_time", tags=["name:test", ANY])

    def test_not_acquired(self):
        fake = FakeLock()
        lock = LockMeter(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as timer:
            self.assertFalse(lock.acquire(blocking=False))
        timer.assert_called_once_with("commcare.lock.acquire_time", tags=["name:test", ANY])

    def test_release(self):
        fake = FakeLock()
        lock = LockMeter(fake, "test")
        lock.acquire()
        with patch("corehq.util.datadog.gauges.datadog_counter") as timer:
            lock.release()
            self.assertFalse(fake.locked)
        timer.assert_called_once_with("commcare.lock.locked_time", tags=["name:test", ANY])

    def test_release_not_locked(self):
        fake = FakeLock()
        lock = LockMeter(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as timer:
            lock.release()
            self.assertFalse(fake.locked)
        timer.assert_not_called()

    def test_lock_as_context_manager(self):
        fake = FakeLock()
        lock = LockMeter(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as timer:
            with lock:
                self.assertTrue(fake.locked)
            self.assertFalse(fake.locked)
        timer.assert_has_calls([
            call("commcare.lock.acquire_time", tags=["name:test", ANY]),
            call("commcare.lock.locked_time", tags=["name:test", ANY]),
        ])
        self.assertEqual(timer.call_count, 2, timer.call_args_list)

    def test_release_failed(self):
        lock = LockMeter(FakeLock(), "test")
        with patch("corehq.util.datadog.lockmeter.datadog_counter") as counter:
            lock.release_failed()
        counter.assert_called_once_with("commcare.lock.release_failed", tags=["name:test"])

    def test_degraded(self):
        lock = LockMeter(FakeLock(), "test")
        with patch("corehq.util.datadog.lockmeter.datadog_counter") as counter:
            lock.degraded()
        counter.assert_called_once_with("commcare.lock.degraded", tags=["name:test"])


class FakeLock(object):

    locked = False

    def acquire(self, blocking=True):
        self.locked = True
        return blocking

    def release(self):
        self.locked = False
