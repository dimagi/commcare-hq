import datetime
import logging

from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    StringProperty,
)
from django.db import models
from django.contrib.postgres.fields import JSONField

from corehq.apps.domain.models import Domain

log = logging.getLogger(__name__)


class RegistrationRequest(models.Model):
    tos_confirmed = models.BooleanField(default=False)
    request_time = models.DateTimeField()
    request_ip = models.CharField(max_length=31, null=True)
    activation_guid = models.CharField(max_length=126, unique=True)
    confirm_time = models.DateTimeField(null=True)
    confirm_ip = models.CharField(max_length=31, null=True)
    domain = models.CharField(max_length=255, null=True)
    new_user_username = models.CharField(max_length=255, null=True)
    requesting_user_username = models.CharField(max_length=255, null=True)
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "registration_registrationrequest"

    @property
    @memoized
    def project(self):
        return Domain.get_by_name(self.domain)

    @classmethod
    def get_by_guid(cls, guid):
        return RegistrationRequest.objects.filter(activation_guid=guid).first()

    @classmethod
    def get_requests_today(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        return RegistrationRequest.objects.filter(
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
        requests = RegistrationRequest.objects.filter(
            request_time__gte=join_on_start,
            request_time__lte=join_on_end,
            confirm_time__isnull=True
        )
        return [req for req in requests if req.new_user_username == req.requesting_user_username]

    @classmethod
    def get_request_for_username(cls, username):
        return RegistrationRequest.objects.filter(new_user_username=username).first()


class AsyncSignupRequest(models.Model):
    """
    Use this model to store information from signup or invitation forms when
    the user is redirected to login elsewhere (like SSO) but the signup/invitation
    process must resume when they return.
    """
    username = models.CharField(max_length=255, db_index=True)
    invitation = models.ForeignKey('users.Invitation', null=True, blank=True, on_delete=models.PROTECT)
    phone_number = models.CharField(max_length=126, null=True, blank=True)
    project_name = models.CharField(max_length=255, null=True, blank=True)
    atypical_user = models.BooleanField(default=False)
    persona = models.CharField(max_length=128, null=True, blank=True)
    persona_other = models.TextField(null=True, blank=True)
    additional_hubspot_data = JSONField(null=True, blank=True)

    @classmethod
    def get_by_username(cls, username):
        try:
            return cls.objects.get(username=username)
        except cls.MultipleObjectsReturned:
            # this would have to be a weird edge case where an error occurred
            # during the signup process. We should log and then triage.
            log.error(
                f"Fetched multiple AsyncSignupRequests for {username}. "
                f"Please check for errors in any auth backends that might "
                f"be interrupting the sign up workflows."
            )
            return cls.objects.first(username=username)
        except cls.DoesNotExist:
            return None
