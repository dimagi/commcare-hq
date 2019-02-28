from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from datetime import timedelta
from six.moves import zip_longest
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.ext.couchdbkit import DateTimeProperty, DocumentSchema
from couchdbkit.exceptions import ResourceConflict
from redis.exceptions import RedisError, LockError
import json
import re
import six
import sys

from corehq.util.datadog.lockmeter import MeteredLock

LOCK_EXPIRATION = timedelta(hours=1)


class LockableMixIn(DocumentSchema):
    lock_date = DateTimeProperty()

    def acquire_lock(self, now):
        """
        Returns True if the lock was acquired by the calling thread,
        False if another thread acquired it first
        """
        if (self.lock_date is None) or (now > (self.lock_date + LOCK_EXPIRATION)):
            try:
                self.lock_date = now
                self.save()
                return True
            except ResourceConflict:
                return False
        else:
            return False

    def release_lock(self):
        assert self.lock_date is not None
        self.lock_date = None
        self.save()


class LockManager(namedtuple('ObjectLockTuple', 'obj lock')):
    """
    A context manager that can also act like a simple tuple
    for dealing with an object and a lock

    The two following examples are equivalent, except that the context manager
    will release the lock even if an error is thrown in the body

    >>> # as a tuple
    >>> obj, lock = LockManager(obj, lock)
    >>> # do stuff...
    >>> if lock:
    ...     release_lock(lock, True)

    >>> # as a context manager
    >>> with LockManager(obj, lock) as obj:
    ...     # do stuff...
    """
    def __enter__(self):
        return self.obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        release_lock(self.lock, degrade_gracefully=True)


class ReleaseOnError(object):
    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            release_lock(self.lock, degrade_gracefully=True)


def get_redis_lock(key, timeout=None, name=None, track_unreleased=True, **kw):
    """Get redis lock with datadog timing metrics

    :param key: Redis lock name.
    :param timeout: Timeout passed through to redis lock.
    :param name: Datadog "lock_name" tag value. This should be just
    specific enough to identify the area of code that acquired the lock,
    but not so specific that it will multiply the number of tags in
    datadog unnecessarily.
    :param track_unreleased: When true (the default), increase the count
    of unreleased locks if a lock object is garbage-collected before it
    is released.
    :param **kw: Keyword arguments to be passed through to redis when
    creating the new lock.
    """
    if name is None:
        raise ValueError("'name' (DataDog 'name' tag value) is required")
    lock = get_redis_client().lock(key, timeout=timeout, **kw)
    return MeteredLock(lock, name, track_unreleased)


def acquire_lock(lock, degrade_gracefully, **kwargs):
    acquired = False
    try:
        acquired = lock.acquire(**kwargs)
    except RedisError:
        if degrade_gracefully:
            if hasattr(lock, "degraded"):
                lock.degraded()
            lock = None
        else:
            raise
    if lock and not acquired:
        if degrade_gracefully:
            if hasattr(lock, "degraded"):
                lock.degraded()
        else:
            raise RedisError("Unable to acquire lock")
    return lock


def release_lock(lock, degrade_gracefully):
    from dimagi.utils.logging import notify_exception
    if lock:
        try:
            try:
                lock.release()
            except BaseException as e:
                exc = sys.exc_info()
                ext = " (already unlocked)" if isinstance(e, LockError) else ""
                try:
                    notify_exception(
                        None,
                        message='Warning: Could not release redis lock%s' % ext,
                        exc_info=exc,
                    )
                except:
                    pass
                six.reraise(*exc)
        except RedisError:
            if degrade_gracefully:
                if hasattr(lock, "release_failed"):
                    lock.release_failed()
            else:
                raise


class RedisLockableMixIn(object):
    @classmethod
    def _redis_obj_lock_key(cls, obj_id):
        """
        This method should return a string representing the name of the key
        that will be used to lock an object of this class.
        """
        return "redis-object-lock-%s-%s" % (cls.__name__, obj_id)

    @classmethod
    def _redis_class_lock_key(cls):
        """
        This method should return a string representing the name of the key
        that will be used to lock access to this class.
        """
        return "redis-class-lock-%s" % cls.__name__

    @classmethod
    def get_obj_id(cls, obj):
        """
        This method should return the unique identifier of the given object.
        """
        raise NotImplementedError("Please implement this method.")

    @classmethod
    def get_obj(cls, *args, **kwargs):
        """
        This method should return an instance of this class matching the passed
        arguments, or None if not found.
        """
        raise NotImplementedError("Please implement this method.")

    @classmethod
    def get_obj_by_id(cls, _id):
        """
        This method should return an instance of this class matching the passed
        id, or None if not found.
        """
        raise NotImplementedError("Please implement this method.")

    @classmethod
    def create_obj(cls, *args, **kwargs):
        """
        This method should create and return an instance of this class using the
        passed arguments.
        """
        raise NotImplementedError("Please implement this method.")

    @classmethod
    def get_latest_obj(cls, obj):
        obj_id = cls.get_obj_id(obj)
        return cls.get_obj_by_id(obj_id)

    @classmethod
    def get_obj_lock(cls, obj, timeout_seconds=120):
        obj_id = cls.get_obj_id(obj)
        return cls.get_redis_lock(cls._redis_obj_lock_key(obj_id), timeout_seconds, obj_id)

    @classmethod
    def get_obj_lock_by_id(cls, obj_id, timeout_seconds=120):
        return cls.get_redis_lock(cls._redis_obj_lock_key(obj_id), timeout_seconds, obj_id)

    @classmethod
    def get_redis_lock(cls, key, timeout_seconds, obj_id=None):
        name = "%s_%s" % (cls.__name__, ("cls" if obj_id is None else "obj"))
        return get_redis_lock(key, timeout=timeout_seconds, name=name)

    @classmethod
    def get_class_lock(cls, timeout_seconds=120):
        return cls.get_redis_lock(cls._redis_class_lock_key(), timeout_seconds)

    @classmethod
    def get_locked_obj(cls, *args, **kwargs):
        """
        Returns a two-tuple containing the object and its lock, which has 
        already been acquired. Once you're finished processing the object, 
        you should call release_lock() on the lock.

        Pass in a kwarg of _id to get the object with get_obj_by_id. Otherwise,
        the object will be retrieved by calling get_obj and passing it all of
        the args.

        Pass in a kwarg of create=True to create the object if it doesn't exist.
        The object will be created calling create_obj and passing it all of the
        args. If create is False or is not set, and if the object doesn't exist,
        (None, None) is returned.
        """
        create = kwargs.pop("create", False)
        _id = kwargs.get("_id", None)
        degrade_gracefully = kwargs.pop('degrade_gracefully', False)
        timeout_seconds = kwargs.pop('timeout_seconds', 120)

        if _id:
            lock = cls.get_obj_lock_by_id(_id, timeout_seconds=timeout_seconds)
        else:
            lock = cls.get_class_lock(timeout_seconds=timeout_seconds)

        lock = acquire_lock(lock, degrade_gracefully, blocking=True)
        try:
            if _id:
                obj = cls.get_obj_by_id(_id)
            else:
                obj = cls.get_obj(*args, **kwargs)
            if not obj:
                if create:
                    obj = cls.create_obj(*args, **kwargs)
                else:
                    release_lock(lock, degrade_gracefully)
                    return LockManager(None, None)
        except:
            release_lock(lock, degrade_gracefully)
            raise
        else:
            if _id:
                return LockManager(obj, lock)
            else:
                obj_lock = cls.get_obj_lock(obj)
                obj_lock = acquire_lock(obj_lock, degrade_gracefully)
                # Refresh the object in case another thread has updated it
                obj = cls.get_latest_obj(obj)
                release_lock(lock, degrade_gracefully)
                return LockManager(obj, obj_lock)


class CouchDocLockableMixIn(RedisLockableMixIn):
    """
    A mixin to prevent document update conflicts and race conditions.
    An example implementation would be:
    
    >>> class Patient(Document, CouchDocLockableMixIn):
            patient_id = StringProperty()
            last_visit = DateProperty()

            @classmethod
            def get_obj(cls, patient_id, *args, **kwargs):
                return Patient.view("patient/by_patient_id",
                                    key=patient_id,
                                    include_docs=True).one()

            @classmethod
            def create_obj(cls, patient_id, *args, **kwargs):
                obj = Patient(patient_id=patient_id)
                obj.save()
                return obj

    >>> # Prevent race condition from creating two patients
    >>> patient, lock = Patient.get_locked_obj("pid-1234", create=True)
    >>> patient.last_visit = date(2014, 1, 24)
    >>> patient.save()
    >>> release_lock(lock, True)

    >>> # Prevent doc update conflict
    >>> patient, lock = Patient.get_locked_obj("pid-1234")
    >>> if not patient:
    >>>     raise RunTimeError("Patient not found")
    >>>
    >>> patient.last_visit = date(2014, 1, 25)
    >>> patient.save()
    >>> release_lock(lock, True)

    >>> # Lookup using couch doc _id
    >>> patient, lock = Patient.get_locked_obj(_id="fa98e2...")
    >>> if not patient:
    >>>     raise RunTimeError("Patient not found")
    >>>
    >>> patient.last_visit = date(2014, 1, 26)
    >>> patient.save()
    >>> release_lock(lock, True)

    >>> # or using 'with' syntax

    >>> with Patient.get_locked_obj("pid-1234", create=True) as patient:
    ...     patient.last_visit = date(2014, 1, 24)
    ...     patient.save()
    ...
    >>> # etc.
    """

    @classmethod
    def get_obj_id(cls, obj):
        return obj._id

    @classmethod
    def get_obj(cls, *args, **kwargs):
        """
        This method should lookup to the appropriate couch view using the
        passed arguments and return the object if found, otherwise None.
        """
        raise NotImplementedError("Please implement this method.")

    @classmethod
    def get_obj_by_id(cls, _id):
        return cls.get(_id)

    @classmethod
    def create_obj(cls, *args, **kwargs):
        """
        This method should create and return an instance of this class using the
        passed arguments.
        """
        raise NotImplementedError("Please implement this method.")


class CriticalSection(object):
    """
    An object to facilitate the use of locking in critical sections where
    you can't use CouchDocLockableMixIn (i.e., in cases where you don't
    necessarily want or need a document to be created).

    Sample usage:
        with CriticalSection(["my-update-key"]):
            ...do processing

    keys - a list of strings representing the keys of the locks to acquire; when
      using multiple keys, make sure to consider key order to prevent deadlock
      and be mindful of the duration of the task(s) using these keys in relation
      to the lock timeout
    fail_hard - if True, exceptions are raised when locks can't be acquired
    timeout - the number of seconds before each lock times out
    block - whether to wait for the lock to be acquired or not
    """
    def __init__(self, keys, fail_hard=False, timeout=60, block=True):
        assert isinstance(keys, (list, tuple))
        self.keys = keys
        self.locks = []
        self.status = []
        self.fail_hard = fail_hard
        self.timeout = timeout
        self.block = block

    def __enter__(self):
        try:
            for key in self.keys:
                name = "_".join(re.split(r"_|-", key, 2)[:2])
                lock = get_redis_lock(key, timeout=self.timeout, name=name)
                self.locks.append(lock)
            for lock in self.locks:
                self.status.append(lock.acquire(blocking=self.block))
        except Exception:
            if self.fail_hard:
                raise
        for lock, status in zip_longest(self.locks, self.status):
            if not status and hasattr(lock, "degraded"):
                lock.degraded()
        return self

    def success(self):
        """Return True if all locks were acquired successfully"""
        return len(self.status) == len(self.locks) and all(self.status)

    def __exit__(self, exc_type, exc_value, traceback):
        for lock in self.locks:
            release_lock(lock, True)


class LooselyEqualDocumentSchema(DocumentSchema):
    """
    A DocumentSchema that will pass equality and hash checks if its
    contents are the same as another document.
    """

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._doc == other._doc

    # TODO - remove this in Python 3
    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(json.dumps(self._doc, sort_keys=True))


class IncompatibleDocument(Exception):
    pass


def get_cached_property(couch_cls, obj_id, prop_name, expiry=12*60*60):
    """
        A function that returns a property of any couch object. If it doesn't find the property in memcached, it does
        the couch query to pull the object and grabs the property. Then it caches the retrieved property.
        Note: The property needs to be pickleable
    """
    from django.core.cache import cache
    cache_str = "{0}:{1}:{2}".format(couch_cls.__name__, obj_id, prop_name)
    ret = cache.get(cache_str)
    if not ret:
        data = couch_cls.get_db().get(obj_id)
        if couch_cls._doc_type in [data.get("doc_type"), data.get("base_doc")]:
            obj = couch_cls.wrap(data)
            ret = getattr(obj, prop_name)
            cache.set(cache_str, ret, expiry)
        else:
            raise IncompatibleDocument("The retrieved document doesn't match the Document Class provided")
    return ret
