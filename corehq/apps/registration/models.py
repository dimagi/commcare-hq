import datetime

from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    StringProperty,
)
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin
from django.db import models

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
        return SQLRegistrationRequest.objects.filter(activation_guid=guid).first()

    @classmethod
    def get_requests_today(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        return SQLRegistrationRequest.objects.filter(
            request_time__gte=yesterday.isoformat(),
            request_time__lte=today.isoformat(),
        ).count()

    @classmethod
    def get_requests_24hrs_ago(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        join_on_start = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day, yesterday.hour, 0, 0, 0)
        join_on_end = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day, yesterday.hour, 59, 59, 59)
        requests = SQLRegistrationRequest.objects.filter(
            request_time__gte=join_on_start,
            request_time__lte=join_on_end,
            confirm_time__isnull=True
        )
        return [req for req in requests if req.new_user_username == req.requesting_user_username]

    @classmethod
    def get_request_for_username(cls, username):
        return SQLRegistrationRequest.objects.filter(new_user_username=username).first()

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
