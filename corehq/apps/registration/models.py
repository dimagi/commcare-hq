import datetime

from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    StringProperty,
)
from django.db import DEFAULT_DB_ALIAS, models

from corehq.apps.domain.models import Domain


class RegistrationRequestMixin():
    @property
    @memoized
    def project(self):
        return Domain.get_by_name(self.domain)


class SQLRegistrationRequest(models.Model, RegistrationRequestMixin):
    tos_confirmed = models.BooleanField(default=False)
    request_time = models.DateTimeField()
    request_ip = models.CharField(max_length=31)
    activation_guid = models.CharField(max_length=126)
    confirm_time = models.DateTimeField(null=True)
    confirm_ip = models.CharField(max_length=31, null=True)
    domain = models.CharField(max_length=255, null=True)
    new_user_username = models.CharField(max_length=255, null=True)
    requesting_user_username = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "registration_registrationrequest"

    def save(self, force_insert=False, force_update=False, using=DEFAULT_DB_ALIAS, update_fields=None):
        # Update or create couch doc
        doc = RegistrationRequest.view("registration/requests_by_guid",
            key=self.activation_guid,
            reduce=False,
            include_docs=True).first()

        if not doc:
            doc = RegistrationRequest(
                activation_guid=self.activation_guid,
                tos_confirmed=self.tos_confirmed,
                request_time=self.request_time,
                request_ip=self.request_ip,
                confirm_time=self.confirm_time,
                confirm_ip=self.confirm_ip,
                domain=self.domain,
                new_user_username=self.new_user_username,
                requesting_user_username=self.requesting_user_username,
            )

        doc.save(from_sql=True)

        # Save to SQL
        super().save(
            force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields
        )


class RegistrationRequest(Document, RegistrationRequestMixin):
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

    def save(self, *args, **kwargs):
        # Save to couch
        # This must happen first so the SQL save finds this doc and doesn't recreate it
        super().save(*args, **kwargs)

        if not kwargs.pop('from_sql', False):
            # Save to SQL
            model, created = SQLRegistrationRequest.objects.update_or_create(
                activation_guid=self.activation_guid,
                defaults={
                    "tos_confirmed": self.tos_confirmed,
                    "request_time": self.request_time,
                    "request_ip": self.request_ip,
                    "confirm_time": self.confirm_time,
                    "confirm_ip": self.confirm_ip,
                    "domain": self.domain,
                    "new_user_username": self.new_user_username,
                    "requesting_user_username": self.requesting_user_username,
                }
            )
