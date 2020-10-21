from django.db import models
from django.utils.translation import ugettext_lazy
from uuid import uuid4
import json

from memoized import memoized

from corehq import toggles


class DialerSettings(models.Model):
    domain = models.CharField(max_length=128, unique=True)
    aws_instance_id = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
    dialer_page_header = models.CharField(max_length=255)
    dialer_page_subheader = models.CharField(max_length=255)


class GaenOtpServerSettings(models.Model):
    SERVER_OPTIONS = (('NEARFORM', ugettext_lazy('Nearform OTP Server')),
                      ('APHL', ugettext_lazy('APHL Exposure Notifications')),)
    domain = models.CharField(max_length=128, unique=True)
    is_enabled = models.BooleanField(default=False)
    server_type = models.CharField(max_length=255, default='NEARFORM', choices=SERVER_OPTIONS)
    server_url = models.CharField(max_length=255)
    auth_token = models.CharField(max_length=255)

    @classmethod
    def get_property_map(cls, server_type):
        property_map = {
            'test_date': 'testDate',
            'test_type': 'testType',
        }
        if server_type == "NEARFORM":
            property_map['phone_number'] = 'mobile'
            property_map['onset_date'] = 'onsetDate'

        elif server_type == "APHL":
            property_map['phone_number'] = 'phone'
            property_map['onset_date'] = 'symptomDate'
            property_map['tz_offset'] = 'tzOffset'
        return property_map

    @classmethod
    def get_post_params(cls, server_type):
        if server_type == "NEARFORM":
            return {'jobId': str(uuid4()), }
        return {}

    @classmethod
    def change_post_data_type(cls, server_type, post_data):
        if server_type == "APHL":
            return json.dumps(post_data)
        return post_data

    @classmethod
    def get_otp_request_headers(cls, server_type, auth_token):
        headers = {}
        if server_type == "NEARFORM":
            headers = {"Authorization": "Bearer %s" % auth_token}

        elif server_type == "APHL":
            headers = {"x-api-key": "%s" % auth_token,
                       "content-type": "application/json",
                       "accept": "application/json"}
        return headers


class HmacCalloutSettings(models.Model):
    domain = models.CharField(max_length=128)
    destination_url = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255)

    class Meta(object):
        unique_together = [
            # HACK work around unique=True implies db_index=True
            # https://code.djangoproject.com/ticket/24082
            # Avoid extra varchar_pattern_ops index
            # since we do not do LIKE queries on these
            # https://stackoverflow.com/a/50926644/10840
            ("domain",),
        ]


class SimprintsIntegration(models.Model):
    domain = models.CharField(max_length=128, unique=True)
    is_enabled = models.BooleanField(default=False)
    project_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)
    module_id = models.CharField(max_length=255)


class ApplicationIntegrationMixin(object):
    """
    Contain all integration options in one place for Application object.
    assumes access to self.domain from Application
    """

    @property
    @memoized
    def is_biometric_enabled(self):
        existing, _ = SimprintsIntegration.objects.get_or_create(
            domain=self.domain,
        )
        return (existing.is_enabled
                and toggles.BIOMETRIC_INTEGRATION.enabled(self.domain))

    @property
    @memoized
    def biometric_context(self):
        config = SimprintsIntegration.objects.get(domain=self.domain)
        return {
            'projectId': config.project_id,
            'userId': config.user_id,
            'moduleId': config.module_id,
            'packageName': 'org.commcare.dalvik',
        }
