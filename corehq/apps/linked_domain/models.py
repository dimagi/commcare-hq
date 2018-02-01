# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import namedtuple

from django.db import models

RemoteLinkDetails = namedtuple('RemoteLinkDetails', 'url_base username api_key')


class DomainLink(models.Model):
    master_domain = models.CharField(max_length=126, null=False)
    linked_domain = models.CharField(max_length=126, null=False)
    last_pull = models.DateTimeField(auto_now_add=True)

    # used for linking across remote instances of HQ
    remote_base_url = models.CharField(max_length=255, null=True)
    remote_username = models.CharField(max_length=255, null=True)
    remote_api_key = models.CharField(max_length=255, null=True)

    class Meta:
        unique_together = ('master_domain', 'linked_domain')

    @classmethod
    def link_domains(cls, master_domain, linked_domain, remote_details=None):
        defaults = {}
        if remote_details:
            defaults['remote_base_url'] = remote_details.url_base
            defaults['remote_username'] = remote_details.username
            defaults['remote_api_key'] = remote_details.api_key

        return cls.objects.get_or_create(
            master_domain=master_domain,
            linked_domain=linked_domain,
            defaults=defaults
        )
