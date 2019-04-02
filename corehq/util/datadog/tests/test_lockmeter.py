from __future__ import absolute_import
from __future__ import unicode_literals
from unittest import TestCase

import attr
from mock import ANY, call, patch

from ..lockmeter import MeteredLock


class TestMeteredLock(TestCase):

    def test_initially_not_locked(self):
        fake = FakeLock()
        MeteredLock(fake, "test")
        self.assertFalse(fake.locked)

    def test_acquire(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as counter:
            lock.acquire()
            self.assertTrue(fake.locked)
        counter.assert_called_once_with("commcare.lock.acquire_time", tags=["lock_name:test", ANY])

    def test_not_acquired(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as counter:
            self.assertFalse(lock.acquire(blocking=False))
        counter.assert_called_once_with("commcare.lock.acquire_time", tags=["lock_name:test", ANY])

    def test_release(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        lock.acquire()
        with patch("corehq.util.datadog.gauges.datadog_counter") as counter:
            lock.release()
            self.assertFalse(fake.locked)
        counter.assert_called_once_with("commcare.lock.locked_time", tags=["lock_name:test", ANY])

    def test_release_not_locked(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as counter:
            lock.release()
            self.assertFalse(fake.locked)
        counter.assert_not_called()

    def test_lock_as_context_manager(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.datadog.gauges.datadog_counter") as counter:
            with lock:
                self.assertTrue(fake.locked)
            self.assertFalse(fake.locked)
        counter.assert_has_calls([
            call("commcare.lock.acquire_time", tags=["lock_name:test", ANY]),
            call("commcare.lock.locked_time", tags=["lock_name:test", ANY]),
        ])
        self.assertEqual(counter.call_count, 2, counter.call_args_list)

    def test_release_failed(self):
        lock = MeteredLock(FakeLock(), "test")
        with patch("corehq.util.datadog.lockmeter.datadog_counter") as counter:
            lock.release_failed()
        counter.assert_called_once_with("commcare.lock.release_failed", tags=["lock_name:test"])

    def test_degraded(self):
        lock = MeteredLock(FakeLock(), "test")
        with patch("corehq.util.datadog.lockmeter.datadog_counter") as counter:
            lock.degraded()
        counter.assert_called_once_with("commcare.lock.degraded", tags=["lock_name:test"])

    def test_released_after_timeout(self):
        lock = MeteredLock(FakeLock(timeout=-1), "test")
        lock.acquire()
        with patch("corehq.util.datadog.lockmeter.datadog_counter") as counter:
            lock.release()
        counter.assert_called_once_with("commcare.lock.released_after_timeout", tags=["lock_name:test"])

    def test_lock_without_timeout(self):
        fake = FakeLock()
        del fake.timeout
        assert not hasattr(fake, "timeout")
        lock = MeteredLock(fake, "test")
        lock.acquire()  # should not raise

    def test_acquire_trace(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.datadog.lockmeter.tracer") as tracer:
            lock.acquire()
        self.assertListEqual(tracer.mock_calls, [
            call.trace("commcare.lock.acquire", resource="key"),
            call.trace().__enter__(),
            call.trace().__enter__().set_tags({
                "key": "key",
                "name": "test",
                "acquired": "true",
            }),
            call.trace().__exit__(None, None, None),
            call.trace("commcare.lock.locked", resource="key"),
            call.trace().set_tags({"key": "key", "name": "test"}),
        ])

    def test_release_trace(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.datadog.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.release()
        self.assertListEqual(tracer.mock_calls, [call.trace().finish()])

    def test_del_trace(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.datadog.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.__del__()
        self.assertListEqual(tracer.mock_calls, [
            call.trace().set_tag("deleted", "not_released"),
            call.trace().finish(),
        ])

    def test_acquire_untracked(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test", track_unreleased=False)
        with patch("corehq.util.datadog.lockmeter.tracer") as tracer:
            lock.acquire()
        self.assertListEqual(tracer.mock_calls, [
            call.trace("commcare.lock.acquire", resource="key"),
            call.trace().__enter__(),
            call.trace().__enter__().set_tags({
                "key": "key",
                "name": "test",
                "acquired": "true",
            }),
            call.trace().__exit__(None, None, None),
        ])

    def test_release_untracked(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test", track_unreleased=False)
        with patch("corehq.util.datadog.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.release()
        self.assertListEqual(tracer.mock_calls, [])

    def test_del_untracked(self):
        fake = FakeLock()
        lock = MeteredLock(fake, "test", track_unreleased=False)
        with patch("corehq.util.datadog.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.__del__()
        self.assertListEqual(tracer.mock_calls, [])


@attr.s
class FakeLock(object):

    locked = False
    name = attr.ib(default="key")
    timeout = attr.ib(default=None)

    def acquire(self, blocking=True):
        self.locked = True
        return blocking

    def release(self):
        self.locked = False
