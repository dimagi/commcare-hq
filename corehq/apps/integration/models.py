from django.db import models
from django.utils.translation import gettext_lazy
from uuid import uuid4
import json

from memoized import memoized

from corehq import toggles
from corehq.apps.integration.kyc.models import KycConfig # noqa
from corehq.apps.integration.payments.models import MoMoConfig # noqa


class DialerSettings(models.Model):
    domain = models.CharField(max_length=128, unique=True)
    aws_instance_id = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
    dialer_page_header = models.CharField(max_length=255)
    dialer_page_subheader = models.CharField(max_length=255)


class GaenOtpServerSettings(models.Model):
    SERVER_OPTIONS = (('NEARFORM', gettext_lazy('NearForm OTP Server')),
                      ('APHL', gettext_lazy('APHL Exposure Notifications')),)
    domain = models.CharField(max_length=128, unique=True)
    is_enabled = models.BooleanField(default=False)
    server_type = models.CharField(max_length=255, default='NEARFORM', choices=SERVER_OPTIONS)
    server_url = models.CharField(max_length=255)
    auth_token = models.CharField(max_length=255)

    def get_property_map(self):
        property_map = {
            'test_date': 'testDate',
            'test_type': 'testType',
        }
        if self.server_type == "NEARFORM":
            property_map['phone_number'] = 'mobile'
            property_map['onset_date'] = 'onsetDate'

        elif self.server_type == "APHL":
            property_map['phone_number'] = 'phone'
            property_map['onset_date'] = 'symptomDate'
            property_map['tz_offset'] = 'tzOffset'
        return property_map

    def get_post_params(self):
        if self.server_type == "NEARFORM":
            return {'jobId': str(uuid4()), }
        return {}

    def change_post_data_type(self, post_data):
        if self.server_type == "APHL":
            return json.dumps(post_data)
        return post_data

    def get_otp_request_headers(self):
        headers = {}
        if self.server_type == "NEARFORM":
            headers = {"Authorization": "Bearer %s" % self.auth_token}

        elif self.server_type == "APHL":
            headers = {"x-api-key": "%s" % self.auth_token,
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
