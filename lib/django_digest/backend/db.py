import logging
_l = logging.getLogger(__name__)

from copy import copy

from django.conf import settings
from django.core import signals
from django import db
from django.db.utils import DEFAULT_DB_ALIAS

# Backwards compatibility
from django_digest.models import (
    _after_authenticate as update_partial_digests,
    _review_partial_digests as review_partial_digests
)
from django_digest.backend.storage import AccountStorage, NonceStorage


class MultiDb(object):
    def __init__(self, using=DEFAULT_DB_ALIAS, create=False):
        self.created = create and not self.is_test_mode()
        if self.created:
            self.connection = self.create_connection(using=using)
        else:
            self.connection = db.connections[using]
        self.init_signals()

    def init_signals(self):
        signals.request_finished.connect(self.close_connection)
        signals.request_started.connect(self.reset_queries)

    def create_connection(self, using=None, **kwargs):
        if using:
            params = copy(db.connections[using].settings_dict)
            params.update(kwargs)
        else:
            params = kwargs
        return db.backend.DatabaseWrapper(params)

    def close_connection(self, **kwargs):
        if self.created and self.connection:
            self.connection.close()

    def reset_queries(self, **kwargs):
        if self.created and self.connection:
            self.connection.queries = []

    def is_test_mode(self):
        # hack - in tests we want to run within the same transaction
        # as the test case to pick up users created there
        from django.core import mail
        return hasattr(mail, 'outbox')

    def commit(self):
        if self.created and self.connection and not self.is_test_mode():
            self.connection._commit()


class FakeMultiDb(MultiDb):
    """For Django < 1.2."""
    def __init__(self):
        self.created = not self.is_test_mode()
        self.connection = self.create_connection()
        self.init_signals()

    def create_connection(self, **kwargs):
        if self.is_test_mode():
            return db.connection
        params = {'DATABASE_HOST': settings.DATABASE_HOST,
                  'DATABASE_NAME': settings.DATABASE_NAME,
                  'DATABASE_OPTIONS': settings.DATABASE_OPTIONS,
                  'DATABASE_PASSWORD': settings.DATABASE_PASSWORD,
                  'DATABASE_PORT': settings.DATABASE_PORT,
                  'DATABASE_USER': settings.DATABASE_USER,
                  'TIME_ZONE': settings.TIME_ZONE}
        params.update(kwargs)
        return db.backend.DatabaseWrapper(params)
