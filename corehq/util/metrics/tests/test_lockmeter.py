from typing import Optional, Any
from unittest import TestCase

import attr
from unittest.mock import call, patch

from corehq.util.metrics.tests.utils import capture_metrics
from ..lockmeter import MeteredLock


class TestMeteredLock(TestCase):

    def test_initially_not_locked(self) -> None:
        fake = FakeLock()
        MeteredLock(fake, "test")
        self.assertFalse(fake.locked)

    def test_acquire(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with capture_metrics() as metrics:
            lock.acquire()
            self.assertTrue(fake.locked)
        self.assertEqual(1, len(metrics.list("commcare.lock.acquire_time")), metrics)

    def test_not_acquired(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with capture_metrics() as metrics:
            self.assertFalse(lock.acquire(blocking=False))
        self.assertEqual(1, len(metrics.list("commcare.lock.acquire_time")), metrics)

    def test_release(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        lock.acquire()
        with capture_metrics() as metrics:
            lock.release()
            self.assertFalse(fake.locked)
        self.assertEqual(1, len(metrics.list("commcare.lock.locked_time")), metrics)

    def test_release_not_locked(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.metrics.metrics_histogram") as counter:
            lock.release()
            self.assertFalse(fake.locked)
        counter.assert_not_called()

    def test_lock_as_context_manager(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with capture_metrics() as metrics:
            with lock:
                self.assertTrue(fake.locked)
            self.assertFalse(fake.locked)
        self.assertEqual(1, len(metrics.list("commcare.lock.acquire_time")), metrics)
        self.assertEqual(1, len(metrics.list("commcare.lock.locked_time")), metrics)

    def test_release_failed(self) -> None:
        lock = MeteredLock(FakeLock(), "test")
        with capture_metrics() as metrics:
            lock.release_failed()
        self.assertEqual(1, len(metrics.list("commcare.lock.release_failed", lock_name='test')), metrics)

    def test_degraded(self) -> None:
        lock = MeteredLock(FakeLock(), "test")
        with capture_metrics() as metrics:
            lock.degraded()
        self.assertEqual(1, len(metrics.list("commcare.lock.degraded", lock_name='test')), metrics)

    def test_released_after_timeout(self) -> None:
        lock = MeteredLock(FakeLock(timeout=-1), "test")
        lock.acquire()
        with capture_metrics() as metrics:
            lock.release()
        self.assertEqual(1, len(metrics.list("commcare.lock.released_after_timeout", lock_name='test')), metrics)

    def test_lock_without_timeout(self) -> None:
        fake = FakeLock()
        del fake.timeout
        assert not hasattr(fake, "timeout")
        lock = MeteredLock(fake, "test")
        lock.acquire()  # should not raise

    def test_acquire_trace(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.metrics.lockmeter.tracer") as tracer:
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

    def test_release_trace(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.metrics.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.release()
        self.assertListEqual(tracer.mock_calls, [call.trace().finish()])

    def test_del_trace(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test")
        with patch("corehq.util.metrics.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.__del__()
        self.assertListEqual(tracer.mock_calls, [
            call.trace().set_tag("deleted", "not_released"),
            call.trace().finish(),
        ])

    def test_acquire_untracked(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test", track_unreleased=False)
        with patch("corehq.util.metrics.lockmeter.tracer") as tracer:
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

    def test_release_untracked(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test", track_unreleased=False)
        with patch("corehq.util.metrics.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.release()
        self.assertListEqual(tracer.mock_calls, [])

    def test_del_untracked(self) -> None:
        fake = FakeLock()
        lock = MeteredLock(fake, "test", track_unreleased=False)
        with patch("corehq.util.metrics.lockmeter.tracer") as tracer:
            lock.acquire()
            tracer.reset_mock()
            lock.__del__()
        self.assertListEqual(tracer.mock_calls, [])


@attr.s
class FakeLock(object):

    locked = False
    name = attr.ib(type=str, default="key")
    timeout = attr.ib(type=Optional[int], default=None)

    def acquire(
        self,
        blocking: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        self.locked = True
        return blocking

    def release(self) -> None:
        self.locked = False
