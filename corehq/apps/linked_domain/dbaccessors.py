# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

from corehq.apps.linked_domain.models import DomainLink
from corehq.util.quickcache import quickcache


@quickcache(['domain'], timeout=60 * 60)
def get_domain_master_link(domain):
    """
    :returns: ``DomainLink`` object linking this domain to it's master
    or None if no link exists
    """
    return DomainLink.objects.filter(linked_domain=domain).first()


@quickcache(['domain'], timeout=60 * 60)
def is_linked_domain(domain):
    return DomainLink.objects.filter(linked_domain=domain).exists()


@quickcache(['domain'], timeout=60 * 60)
def get_linked_domains(domain):
    """
    :param domain:
    :return: List of ``DomainLink`` objects for each domain linked to this one.
    """
    return list(DomainLink.all_objects.filter(master_domain=domain).all())


@quickcache(['domain'], timeout=60 * 60)
def is_master_linked_domain(domain):
    return DomainLink.objects.filter(master_domain=domain).exists()
