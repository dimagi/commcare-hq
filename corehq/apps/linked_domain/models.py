from collections import namedtuple
from datetime import datetime

from django.db import models
from django.db.transaction import atomic
from django.urls import reverse
from django.utils.translation import gettext as _

import jsonobject

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.linked_domain.const import ALL_LINKED_MODELS
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.privileges import RELEASE_MANAGEMENT


class RemoteLinkDetails(namedtuple('RemoteLinkDetails', 'url_base username api_key')):
    def __bool__(self):
        return bool(self.url_base)

    __nonzero__ = __bool__


class ExcludeDeletedManager(models.Manager):
    def get_queryset(self):
        return super(ExcludeDeletedManager, self).get_queryset().filter(deleted=False)


class DomainLink(models.Model):
    linked_domain = models.CharField(max_length=126, null=False)
    master_domain = models.CharField(max_length=126, null=False)
    last_pull = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)

    # used for linking across remote instances of HQ
    remote_base_url = models.CharField(max_length=255, null=True, blank=True,
                                       help_text=_("should be the full link without the trailing /. "
                                                   "Example: https://www.commcarehq.org"))
    remote_username = models.CharField(max_length=255, null=True, blank=True)
    remote_api_key = models.CharField(max_length=255, null=True, blank=True)

    objects = ExcludeDeletedManager()
    all_objects = models.Manager()

    @property
    def upstream_url(self):
        if self.is_remote:
            return '{}{}'.format(
                self.remote_base_url,
                reverse('domain_homepage', args=[self.master_domain])
            )
        else:
            return reverse('domain_links', args=[self.master_domain])

    @property
    def downstream_url(self):
        if self.is_remote:
            return self.linked_domain
        else:
            return reverse('domain_links', args=[self.linked_domain])

    @property
    def remote_details(self):
        return RemoteLinkDetails(self.remote_base_url, self.remote_username, self.remote_api_key)

    @property
    def is_remote(self):
        return bool(self.remote_base_url) or 'http' in self.linked_domain

    def has_full_access(self):
        return (domain_has_privilege(self.master_domain, RELEASE_MANAGEMENT)
                and domain_has_privilege(self.linked_domain, RELEASE_MANAGEMENT))

    @atomic
    def update_last_pull(self, model, user_id, date=None, model_detail=None):
        self.last_pull = date or datetime.utcnow()
        self.save()
        history = DomainLinkHistory(link=self, date=self.last_pull, user_id=user_id, model=model)
        if model_detail:
            history.model_detail = model_detail
        history.save()

    def save(self, *args, **kwargs):
        super(DomainLink, self).save(*args, **kwargs)
        from corehq.apps.linked_domain.dbaccessors import (
            get_linked_domains,
            get_upstream_domain_link,
            is_active_downstream_domain,
            is_active_upstream_domain,
        )
        get_upstream_domain_link.clear(self.linked_domain)
        is_active_downstream_domain.clear(self.linked_domain)

        get_linked_domains.clear(self.master_domain)
        is_active_upstream_domain.clear(self.master_domain)

    @classmethod
    def link_domains(cls, linked_domain, master_domain, remote_details=None):
        """
        With the GAing of linked projects in the form of ERM/MRM, this will become an internal method in favor
        of the link_domains method in linked_domain/views.py to allow for proper validation of domain and user
        privileges before creating any links
        """
        existing_links = cls.all_objects.filter(linked_domain=linked_domain)
        active_links_with_other_domains = [
            domain_link for domain_link in existing_links
            if not domain_link.deleted and domain_link.master_domain != master_domain
        ]
        if active_links_with_other_domains:
            already_linked_domain = active_links_with_other_domains[0].master_domain
            raise DomainLinkError(
                _('{} is already a downstream project space of {}.\nYou must remove the existing link before '
                  'creating this new link.').format(linked_domain, already_linked_domain)
            )

        deleted_existing_links = [
            domain_link for domain_link in existing_links
            if domain_link.deleted and domain_link.master_domain == master_domain
        ]
        active_links_with_this_domain = [
            domain_link for domain_link in existing_links
            if not domain_link.deleted and domain_link.master_domain == master_domain
        ]

        if deleted_existing_links:
            # if there was a deleted link, just undelete it
            link = deleted_existing_links[0]
            link.deleted = False
        elif active_links_with_this_domain:
            # if there is already an active link, just update it with the new information
            link = active_links_with_this_domain[0]
        else:
            link = DomainLink(linked_domain=linked_domain, master_domain=master_domain)

        if remote_details:
            link.remote_base_url = remote_details.url_base
            link.remote_username = remote_details.username
            link.remote_api_key = remote_details.api_key

        link.save()
        return link


class VisibleDomainLinkHistoryManager(models.Manager):
    def get_queryset(self):
        return super(VisibleDomainLinkHistoryManager, self).get_queryset().filter(hidden=False)


class DomainLinkHistory(models.Model):
    link = models.ForeignKey(DomainLink, on_delete=models.CASCADE, related_name='history')
    date = models.DateTimeField(null=False)
    model = models.CharField(max_length=128, choices=ALL_LINKED_MODELS, null=False)
    model_detail = models.JSONField(null=True, blank=True)
    user_id = models.CharField(max_length=255, null=False)
    hidden = models.BooleanField(default=False)

    objects = VisibleDomainLinkHistoryManager()
    all_objects = models.Manager()

    @property
    def wrapped_detail(self):
        if self.model_detail:
            return wrap_detail(self.model, self.model_detail)

    class Meta(object):
        ordering = ("-date",)


class AppLinkDetail(jsonobject.JsonObject):
    app_id = jsonobject.StringProperty()


class FixtureLinkDetail(jsonobject.JsonObject):
    tag = jsonobject.StringProperty()


class UpdateRuleLinkDetail(jsonobject.JsonObject):
    id = jsonobject.IntegerProperty()


class ReportLinkDetail(jsonobject.JsonObject):
    report_id = jsonobject.StringProperty()


class KeywordLinkDetail(jsonobject.JsonObject):
    keyword_id = jsonobject.StringProperty()


class UCRExpressionLinkDetail(jsonobject.JsonObject):
    ucr_expression_id = jsonobject.StringProperty()


def wrap_detail(model, detail_json):
    return {
        'app': AppLinkDetail,
        'fixture': FixtureLinkDetail,
        'report': ReportLinkDetail,
        'keyword': KeywordLinkDetail,
        'ucr_expression': UCRExpressionLinkDetail,
        'auto_update_rule': UpdateRuleLinkDetail,
    }[model].wrap(detail_json)
