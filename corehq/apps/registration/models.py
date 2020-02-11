import datetime

from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    StringProperty,
)
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin
from django.db import DEFAULT_DB_ALIAS, models

from corehq.apps.domain.models import Domain


class RegistrationRequestMixin():
    @property
    @memoized
    def project(self):
        return Domain.get_by_name(self.domain)


class SQLRegistrationRequest(SyncSQLToCouchMixin, models.Model, RegistrationRequestMixin):
    tos_confirmed = models.BooleanField(default=False)
    request_time = models.DateTimeField()
    request_ip = models.CharField(max_length=31)
    activation_guid = models.CharField(max_length=126, unique=True)
    confirm_time = models.DateTimeField(null=True)
    confirm_ip = models.CharField(max_length=31, null=True)
    domain = models.CharField(max_length=255, null=True)
    new_user_username = models.CharField(max_length=255, null=True)
    requesting_user_username = models.CharField(max_length=255, null=True)
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "registration_registrationrequest"

    @classmethod
    def _migration_get_fields(cls):
        return [
            "tos_confirmed",
            "request_time",
            "request_ip",
            "activation_guid",
            "confirm_time",
            "confirm_ip",
            "domain",
            "new_user_username",
            "requesting_user_username",
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return RegistrationRequest


class RegistrationRequest(SyncCouchToSQLMixin, Document, RegistrationRequestMixin):
    tos_confirmed = BooleanProperty(default=False)
    request_time = DateTimeProperty()
    request_ip = StringProperty()
    activation_guid = StringProperty()
    confirm_time = DateTimeProperty()
    confirm_ip = StringProperty()
    domain = StringProperty()
    new_user_username = StringProperty()
    requesting_user_username = StringProperty()

    @classmethod
    def get_by_guid(cls, guid):
        result = cls.view("registration/requests_by_guid",
            key=guid,
            reduce=False,
            include_docs=True).first()
        return result

    @classmethod
    def get_requests_today(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        result = cls.view("registration/requests_by_time",
            startkey=yesterday.isoformat(),
            endkey=today.isoformat(),
            reduce=True).all()
        if not result:
            return 0
        return result[0]['value']

    @classmethod
    def get_requests_24hrs_ago(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        join_on_start = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day, yesterday.hour, 0, 0, 0)
        join_on_end = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day, yesterday.hour, 59, 59, 59)
        result = cls.view(
            "registration/requests_by_time",
            startkey=join_on_start.isoformat(),
            endkey=join_on_end.isoformat(),
            include_docs=True,
            reduce=False
        ).all()
        return [doc for doc in result if (doc.new_user_username == doc.requesting_user_username
                         and doc.confirm_time is None)]

    @classmethod
    def get_request_for_username(cls, username):
        result = cls.view("registration/requests_by_username",
            key=username,
            reduce=False,
            include_docs=True).first()
        return result

    @classmethod
    def _migration_get_fields(cls):
        return [
            "tos_confirmed",
            "request_time",
            "request_ip",
            "activation_guid",
            "confirm_time",
            "confirm_ip",
            "domain",
            "new_user_username",
            "requesting_user_username",
        ]

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLRegistrationRequest
