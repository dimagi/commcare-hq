from __future__ import absolute_import

from memoized import memoized
from corehq import toggles

from django.db import models


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
