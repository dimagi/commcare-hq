from django.db.models.expressions import RawSQL

from corehq import toggles
from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.models import Domain
from corehq.apps.linked_domain.models import DomainLink, DomainLinkHistory
from corehq.privileges import LINKED_PROJECTS
from corehq.util.quickcache import quickcache


@quickcache(['domain'], timeout=60 * 60)
def get_domain_master_link(domain):
    """
    :returns: ``DomainLink`` object linking this domain to it's master
    or None if no link exists
    """
    return DomainLink.objects.filter(linked_domain=domain).first()


@quickcache(['domain'], timeout=60 * 60)
def is_active_upstream_domain(domain):
    return DomainLink.objects.filter(master_domain=domain).exists()


@quickcache(['domain'], timeout=60 * 60)
def is_active_downstream_domain(domain):
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


def get_available_domains_to_link(upstream_domain_name, user):
    """
    This supports both the old feature flagged version of linked projects and the GAed version
    The GAed version is only available to enterprise customers and only usable by admins, but the feature flagged
    version is available to anyone who can obtain access (the wild west)
    :param upstream_domain_name: potential upstream domain candidate
    :param user: user object
    :return: list of domain names available to link as downstream projects
    """
    def _is_domain_available(for_user, domain_name, should_limit_to_admin=True):
        if domain_name == upstream_domain_name:
            return False

        if is_active_downstream_domain(domain_name) or is_active_upstream_domain(domain_name):
            # caanot link to an already linked project
            return False

        upstream_membership = for_user.get_domain_membership(upstream_domain_name)
        downstream_membership = for_user.get_domain_membership(domain_name)
        if should_limit_to_admin:
            is_upstream_admin = upstream_membership.is_admin if upstream_membership else False
            is_downstream_admin = downstream_membership.is_admin if downstream_membership else False
            return is_upstream_admin and is_downstream_admin
        else:
            return True

    current_subscription = Subscription.get_active_subscription_by_domain(upstream_domain_name)
    if current_subscription and domain_has_privilege(upstream_domain_name, LINKED_PROJECTS):
        eligible_domains = [d for d in current_subscription.account.get_domains()]
        return list({d for d in eligible_domains if _is_domain_available(user, d)})
    elif toggles.LINKED_DOMAINS.enabled(upstream_domain_name):
        eligible_domains = [d.name for d in Domain.active_for_user(user)]
        return list({d for d in eligible_domains if _is_domain_available(user, d, should_limit_to_admin=False)})

    return []
