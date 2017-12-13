from __future__ import absolute_import
import threading

from django.conf import settings

from corehq.apps.domain_migration_flags.api import (
    set_migration_started, set_migration_not_started,
    set_migration_complete, get_migration_complete,
    get_migration_status, migration_in_progress
)
from corehq.apps.domain_migration_flags.models import MigrationStatus
from corehq.util.soft_assert import soft_assert
from corehq.util.view_utils import get_request

TZMIGRATION_SLUG = 'tzmigration'


def set_tz_migration_started(domain):
    return set_migration_started(domain, TZMIGRATION_SLUG)


def set_tz_migration_not_started(domain):
    return set_migration_not_started(domain, TZMIGRATION_SLUG)


def set_tz_migration_complete(domain):
    set_migration_complete(domain, TZMIGRATION_SLUG)


def get_tz_migration_complete(domain):
    return get_migration_complete(domain, TZMIGRATION_SLUG)


def get_tz_migration_status(domain, strict=False):
    return get_migration_status(domain, TZMIGRATION_SLUG, strict=strict)


def timezone_migration_in_progress(domain):
    return migration_in_progress(domain, TZMIGRATION_SLUG)


def phone_timezones_have_been_processed():
    """
    The timezone data migration happening some time in Apr-May 2015
    will shift all phone times (form.timeEnd, case.modified_on, etc.) to UTC
    so functions that deal with converting to or from phone times
    use this function to decide what type of timezone conversion is necessary

    """
    if settings.UNIT_TESTING:
        override = getattr(
            settings, 'PHONE_TIMEZONES_HAVE_BEEN_PROCESSED', None)
        if override is not None:
            return override
    return (_get_migration_status_from_threadlocals()
            == MigrationStatus.COMPLETE)


def phone_timezones_should_be_processed():
    try:
        if _thread_local._force_phone_timezones_should_be_processed:
            return True
    except AttributeError:
        pass

    if settings.UNIT_TESTING:
        override = getattr(
            settings, 'PHONE_TIMEZONES_SHOULD_BE_PROCESSED', None)
        if override is not None:
            return override
    return _get_migration_status_from_threadlocals() in (
        MigrationStatus.IN_PROGRESS, MigrationStatus.COMPLETE)


_thread_local = threading.local()


class _ForcePhoneTimezonesShouldBeProcessed(object):

    def __enter__(self):
        try:
            self.orig = _thread_local._force_phone_timezones_should_be_processed
        except AttributeError:
            self.orig = False
        _thread_local._force_phone_timezones_should_be_processed = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        _thread_local._force_phone_timezones_should_be_processed = self.orig


def force_phone_timezones_should_be_processed():
    return _ForcePhoneTimezonesShouldBeProcessed()


def _get_migration_status_from_threadlocals():
    _default = MigrationStatus.NOT_STARTED
    _assert = soft_assert(['droberts' + '@' + 'dimagi.com'])
    try:
        request = get_request()
        try:
            domain = request.domain
        except AttributeError:
            return _default
        return get_tz_migration_status(domain)
    except Exception as e:
        _assert(False, 'Error in _get_migration_status', e)
        return _default
