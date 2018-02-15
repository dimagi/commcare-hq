# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from collections import namedtuple
from datetime import datetime

import jsonobject
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.transaction import atomic
from django.urls import reverse

from corehq.apps.linked_domain.const import LINKED_MODELS
from corehq.apps.linked_domain.exceptions import DomainLinkError


class RemoteLinkDetails(namedtuple('RemoteLinkDetails', 'url_base username api_key')):
    def __bool__(self):
        return bool(self.url_base)

    __nonzero__ = __bool__


class ExcludeDeletedManager(models.Manager):
    def get_queryset(self):
        return super(ExcludeDeletedManager, self).get_queryset().filter(deletd=False)


class DomainLink(models.Model):
    linked_domain = models.CharField(max_length=126, null=False)
    master_domain = models.CharField(max_length=126, null=False)
    last_pull = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)

    # used for linking across remote instances of HQ
    remote_base_url = models.CharField(max_length=255, null=True, blank=True)
    remote_username = models.CharField(max_length=255, null=True, blank=True)
    remote_api_key = models.CharField(max_length=255, null=True, blank=True)

    objects = ExcludeDeletedManager()
    all_objects = models.Manager()

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

    def save(self, *args, **kwargs):
        super(DomainLink, self).save(*args, **kwargs)
        from corehq.apps.linked_domain.dbaccessors import get_domain_master_link, get_linked_domains
        get_domain_master_link.clear(self.linked_domain)
        get_linked_domains.clear(self.master_domain)

    @classmethod
    def link_domains(cls, linked_domain, master_domain, remote_details=None):
        try:
            link = cls.all_objects.get(linked_domain=linked_domain)
        except cls.DoesNotExist:
            link = DomainLink(linked_domain=linked_domain, master_domain=master_domain)
        else:
            if link.master_domain != master_domain:
                if link.deleted:
                    # create a new link to the new master domain
                    link = DomainLink(linked_domain=linked_domain, master_domain=master_domain)
                else:
                    raise DomainLinkError('Domain "{}" is already linked to a different domain ({}).'.format(
                        linked_domain, link.master_domain
                    ))

        if remote_details:
            link.remote_base_url = remote_details.url_base
            link.remote_username = remote_details.username
            link.remote_api_key = remote_details.api_key

        link.deleted = False
        link.save()
        return link


class DomainLinkHistory(models.Model):
    link = models.ForeignKey(DomainLink, on_delete=models.CASCADE, related_name='history')
    date = models.DateTimeField(null=False)
    model = models.CharField(max_length=128, choices=LINKED_MODELS, null=False)
    model_detail = JSONField(null=True, blank=True)
    user_id = models.CharField(max_length=255, null=False)

    @property
    def wrapped_detail(self):
        if self.model_detail:
            return wrap_detail(self.model, self.model_detail)

    class Meta:
        ordering = ("-date",)


class AppLinkDetail(jsonobject.JsonObject):
    app_id = jsonobject.StringProperty()


def wrap_detail(model, detail_json):
    return {
        'app': AppLinkDetail
    }[model].wrap(detail_json)
