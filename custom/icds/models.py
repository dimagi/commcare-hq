from __future__ import absolute_import, unicode_literals

import jsonfield
from django.db import models
from django.utils.functional import cached_property
from django.contrib import admin
from corehq.motech.utils import b64_aes_decrypt


class CCZHosting(models.Model):
    identifier = models.CharField(null=False, unique=True, max_length=255)
    app_versions = jsonfield.JSONField(default=dict)
    username = models.CharField(null=False, max_length=255)
    password = models.CharField(null=False, max_length=255)

    @cached_property
    def get_password(self):
        return b64_aes_decrypt(self.password)


admin.site.register(CCZHosting)
