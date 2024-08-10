from datetime import datetime
from unittest import expectedFailure
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.pg_lock.models import Lock, lock
from dimagi.utils.couch import get_redis_lock, get_pg_lock


class PGLockTests(TestCase):

    def test_acquires_lock_when_not_locked(self):
        lock_instance = Lock('test_lock')
        acquired = lock_instance.acquire(blocking=False)
        self.assertTrue(acquired)
        self.assertTrue(lock_instance.locked())
        lock_instance.release()

    def test_does_not_acquire_lock_when_already_locked(self):
        lock_instance = Lock('test_lock')
        lock_instance.acquire(blocking=False)
        another_lock_instance = Lock('test_lock')
        acquired = another_lock_instance.acquire(blocking=False)
        self.assertFalse(acquired)
        lock_instance.release()

    def test_releases_lock(self):
        lock_instance = Lock('test_lock')
        lock_instance.acquire(blocking=False)
        lock_instance.release()
        self.assertFalse(lock_instance.locked())

    def test_releases_lock_not_acquired(self):
        lock_instance = Lock('test_lock')
        lock_instance.acquire(blocking=False)
        another_lock_instance = Lock('test_lock')
        another_lock_instance.release()
        self.assertFalse(lock_instance.locked())

    @patch('corehq.apps.pg_lock.models.datetime')
    def test_acquires_lock_after_expiration(self, mock_datetime):
        lock_instance = Lock('test_lock')
        mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
        lock_instance.acquire(blocking=False, timeout=1)
        mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 2)
        acquired = lock_instance.acquire(blocking=False)
        self.assertTrue(acquired)
        lock_instance.release()

    def test_context_manager_acquires_and_releases_lock(self):
        with lock('test_lock') as acquired:
            self.assertTrue(acquired)
            lock_instance = Lock('test_lock')
            self.assertTrue(lock_instance.locked())
        lock_instance = Lock('test_lock')
        self.assertFalse(lock_instance.locked())


class TestLockWorkers(TestCase):

    @expectedFailure
    def test_release_redis_lock_not_acquired(self):
        # Worker 1:
        lock1 = get_redis_lock('test-key', timeout=1, name='test-name')
        self.assertTrue(lock1.acquire(blocking=False))
        self.assertTrue(lock1.locked())

        # Worker 2:
        lock2 = get_redis_lock('test-key', timeout=1, name='test-name')
        lock2.release()  # redis.exceptions.LockError: Cannot release an unlocked lock

        self.assertFalse(lock1.locked())

    def test_release_pg_lock_not_acquired(self):
        # Worker 1:
        lock1 = get_pg_lock('test-key', name='test-name')
        self.assertTrue(lock1.acquire(blocking=False))
        self.assertTrue(lock1.locked())

        # Worker 2:
        lock2 = get_pg_lock('test-key', name='test-name')
        lock2.release()

        self.assertFalse(lock1.locked())
