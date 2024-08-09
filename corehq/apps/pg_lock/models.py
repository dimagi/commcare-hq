"""
A partial implementation of a lock using PostgreSQL. It does not
implement blocking.

The intention of using Postgres for locking is to have a lock that can
be used for coordinating across multiple worker processes.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

from django.db import models, IntegrityError


class PGLock(models.Model):
    key = models.CharField(max_length=255, primary_key=True)
    expires_at = models.DateTimeField(null=True, blank=True)


class Lock:
    def __init__(self, key):
        self.key = key

    def __str__(self):
        return self.key

    @property
    def name(self):  # Used by MeteredLock
        return self.key

    def acquire(self, blocking=True, timeout=-1):
        if blocking:
            raise NotImplementedError("Blocking is not supported")

        if timeout >= 0:
            expires_at = datetime.utcnow() + timedelta(seconds=timeout)
        else:
            expires_at = None

        try:
            pg_lock, created = PGLock.objects.get_or_create(
                key=self.key,
                defaults={'expires_at': expires_at},
            )
            if created:
                return True
            if (
                pg_lock.expires_at is not None
                and pg_lock.expires_at <= datetime.utcnow()
            ):
                # Lock has expired
                pg_lock.expires_at = expires_at
                pg_lock.save()
                return True
            return False
        except IntegrityError:
            return False

    def release(self):
        PGLock.objects.filter(key=self.key).delete()

    def locked(self):
        return (
            PGLock.objects
            .filter(key=self.key)
            .filter(
                models.Q(expires_at__isnull=True)
                | models.Q(expires_at__gt=datetime.utcnow())
            )
            .exists()
        )


@contextmanager
def lock(key, timeout=-1):
    lock = Lock(key)
    acquired = False
    try:
        acquired = lock.acquire(blocking=False, timeout=timeout)
        yield acquired
    finally:
        if acquired:
            lock.release()
