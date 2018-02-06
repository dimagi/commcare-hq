# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import namedtuple

from django.db import models

from corehq.apps.linked_domain.exceptions import DomainLinkError


class RemoteLinkDetails(namedtuple('RemoteLinkDetails', 'url_base username api_key')):
    def __bool__(self):
        return bool(self.url_base)

    __nonzero__ = __bool__


class DomainLink(models.Model):
    linked_domain = models.CharField(max_length=126, null=False, unique=True)
    master_domain = models.CharField(max_length=126, null=False)
    last_pull = models.DateTimeField(auto_now_add=True)

    # used for linking across remote instances of HQ
    remote_base_url = models.CharField(max_length=255, null=True)
    remote_username = models.CharField(max_length=255, null=True)
    remote_api_key = models.CharField(max_length=255, null=True)

    @property
    def remote_details(self):
        return RemoteLinkDetails(self.remote_base_url, self.remote_username, self.remote_api_key)

    @property
    def is_remote(self):
        return bool(self.remote_base_url)

    @classmethod
    def link_domains(cls, linked_domain, master_domain, remote_details=None):
        try:
            link = cls.objects.get(linked_domain=linked_domain)
        except cls.DoesNotExist:
            link = DomainLink(linked_domain=linked_domain, master_domain=master_domain)

        if link.master_domain != master_domain:
            raise DomainLinkError('Domain "{}" is already linked to a different domain ({}).'.format(
                linked_domain, link.master_domain
            ))

        if remote_details:
            link.remote_base_url = remote_details.url_base
            link.remote_username = remote_details.username
            link.remote_api_key = remote_details.api_key
        link.save()

        from corehq.apps.linked_domain.dbaccessors import get_domain_master_link, get_linked_domains
        get_domain_master_link.clear(linked_domain)
        get_linked_domains.clear(master_domain)
        return link
