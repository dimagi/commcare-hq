# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import namedtuple

from datetime import datetime

import jsonobject
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.transaction import atomic
from django.urls import reverse

from corehq.apps.linked_domain.const import LINKED_MODELS
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.util.view_utils import absolute_reverse


class RemoteLinkDetails(namedtuple('RemoteLinkDetails', 'url_base username api_key')):
    def __bool__(self):
        return bool(self.url_base)

    __nonzero__ = __bool__


class DomainLink(models.Model):
    linked_domain = models.CharField(max_length=126, null=False, unique=True)
    master_domain = models.CharField(max_length=126, null=False)
    last_pull = models.DateTimeField(null=True)

    # used for linking across remote instances of HQ
    remote_base_url = models.CharField(max_length=255, null=True)
    remote_username = models.CharField(max_length=255, null=True)
    remote_api_key = models.CharField(max_length=255, null=True)

    @property
    def qualified_master(self):
        if self.is_remote:
            return '{}{}'.format(
                self.remote_base_url,
                reverse('domain_homepage', args=[self.master_domain])
            )
        else:
            return self.master_domain

    @property
    def remote_details(self):
        return RemoteLinkDetails(self.remote_base_url, self.remote_username, self.remote_api_key)

    @property
    def is_remote(self):
        return bool(self.remote_base_url)

    @atomic
    def update_last_pull(self, model, user_id, date=None, model_details=None):
        self.last_pull = date or datetime.utcnow()
        self.save()
        history = DomainLinkHistory(link=self, date=self.last_pull, user_id=user_id, model=model)
        if model_details:
            history.model_detail = model_details.to_json()
        history.save()

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


class DomainLinkHistory(models.Model):
    link = models.ForeignKey(DomainLink, on_delete=models.CASCADE, related_name='history')
    date = models.DateTimeField(null=False)
    model = models.CharField(max_length=128, choices=LINKED_MODELS, null=False)
    model_detail = JSONField(null=True)
    user_id = models.CharField(max_length=255, null=False)

    class Meta:
        ordering = ("-date",)


class AppLinkDetail(jsonobject.JsonObject):
    app_id = jsonobject.StringProperty()


def wrap_detail(model, detail_json):
    return {
        'app': AppLinkDetail
    }[model].wrap(detail_json)
