from django.db.models.expressions import RawSQL

from corehq.apps.linked_domain.models import DomainLink, DomainLinkHistory
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
def get_linked_domains(domain, include_deleted=False):
    """
    :param domain:
    :return: List of ``DomainLink`` objects for each domain linked to this one.
    """
    manager = DomainLink.all_objects if include_deleted else DomainLink.objects
    return list(manager.filter(master_domain=domain).all())


@quickcache(['domain'], timeout=60 * 60)
def is_master_linked_domain(domain):
    return DomainLink.objects.filter(master_domain=domain).exists()


def get_actions_in_domain_link_history(link):
    return DomainLinkHistory.objects.filter(link=link).annotate(row_number=RawSQL(
        'row_number() OVER (PARTITION BY model, model_detail ORDER BY date DESC)',
        []
    ))
