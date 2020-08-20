from django.db import models

from memoized import memoized

from corehq import toggles


class DialerSettings(models.Model):
    domain = models.CharField(max_length=128, unique=True)
    aws_instance_id = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
    dialer_page_header = models.CharField(max_length=255)
    dialer_page_subheader = models.CharField(max_length=255)

class GaenOtpServerSettings(models.Model):
    domain = models.CharField(max_length=128, unique=True)
    is_enabled = models.BooleanField(default=False)
    server_url = models.CharField(max_length=255)
    auth_token = models.CharField(max_length=255)


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
