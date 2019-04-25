from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models
from django.utils.functional import cached_property

from corehq.motech.utils import b64_aes_decrypt
from custom.icds.validators import (
    LowercaseAlphanumbericValidator,
)


class CCZHostingLink(models.Model):
    identifier = models.CharField(null=False, unique=True, max_length=255, db_index=True,
                                  validators=[LowercaseAlphanumbericValidator])
    username = models.CharField(null=False, max_length=255)
    # b64_aes_encrypt'ed raw password is stored in DB
    password = models.CharField(null=False, max_length=255)
    domain = models.CharField(null=False, max_length=255)

    def __str__(self):
        return self.identifier

    @cached_property
    def get_password(self):
        return b64_aes_decrypt(self.password)


class CCZHosting(models.Model):
    link = models.ForeignKey(CCZHostingLink, on_delete=models.CASCADE)
    app_id = models.CharField(max_length=255, null=False)
    version = models.IntegerField(null=False)
