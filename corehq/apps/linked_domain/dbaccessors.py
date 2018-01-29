# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from corehq.apps.linked_domain.models import DomainLink
from corehq.util.quickcache import quickcache


@quickcache(['domain'], timeout=60 * 60)
def get_domain_master_link(domain):
    """
    :returns: ``DomainLink`` object linking this domain to it's master
    or None if no link exists
    """
    link_docs = DomainLink.view(
        'linked_domain/by_domain',
        start_key=[domain, 'linked'],
        end_key=[domain, 'linked', {}],
        include_docs=True,
    )
    if len(link_docs) > 1:
        raise Exception("Multiple docs linking domain '{}' to master domains: {}".format(
            domain, ','.join([link.master_domain for link in link_docs])
        ))
    if link_docs:
        return link_docs[0]


@quickcache(['domain'], timeout=60 * 60)
def get_linked_domains(domain):
    """
    :param domain:
    :return: List of ``DomainLink`` objects for each domain linked to this one.
    """
    return DomainLink.view(
        'linked_domain/by_domain',
        start_key=[domain, 'master'],
        end_key=[domain, 'master', {}],
        include_docs=True,
    )
