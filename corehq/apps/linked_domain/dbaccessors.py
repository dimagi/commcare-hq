from django.db.models.expressions import RawSQL

from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.models import Domain
from corehq.apps.linked_domain.models import DomainLink, DomainLinkHistory
from corehq.apps.linked_domain.util import (
    is_available_upstream_domain,
    is_domain_available_to_link,
    user_has_admin_access_in_all_domains,
)
from corehq.privileges import RELEASE_MANAGEMENT
from corehq.util.quickcache import quickcache


@quickcache(['domain'], timeout=60 * 60)
def get_upstream_domain_link(domain):
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


def get_available_domains_to_link(upstream_domain_name, user, billing_account=None):
    """
    This supports both the old feature flagged version of linked projects and the GAed version
    The GAed version is only available to enterprise customers and only usable by admins, but the feature flagged
    version is available to anyone who can obtain access (the wild west)
    :param upstream_domain_name: potential upstream domain candidate
    :param user: user object
    :param billing_account: optional parameter to limit available domains to within an enterprise account
    :return: list of domain names available to link as downstream projects
    """
    if domain_has_privilege(upstream_domain_name, RELEASE_MANAGEMENT):
        return get_available_domains_to_link_for_account(upstream_domain_name, user, billing_account)
    elif toggles.LINKED_DOMAINS.enabled(upstream_domain_name):
        return get_available_domains_to_link_for_user(upstream_domain_name, user)

    return []


def get_available_domains_to_link_for_account(upstream_domain_name, user, account):
    """
    Finds available domains to link based on domains associated with the provided account
    """
    eligible_domains = account.get_domains() if account else []
    return list({domain for domain in eligible_domains
                 if is_domain_available_to_link(upstream_domain_name, domain, user)})


def get_available_domains_to_link_for_user(upstream_domain_name, user):
    """
    Finds available domains to link based on domains that the provided user is active in
    """
    potential_domains = [d.name for d in Domain.active_for_user(user)]
    return list({potential_domain for potential_domain in potential_domains if is_domain_available_to_link(
        upstream_domain_name, potential_domain, user, should_enforce_admin=False)})


def get_available_upstream_domains_for_downstream_domain(domain_name, user, billing_account=None):
    """
    This supports both the old feature flagged version of linked projects and the GAed version
    The GAed version is only available to enterprise customers and only usable by admins, but the feature flagged
    version is available to anyone who can obtain access (the wild west)
    :param domain_name: potential upstream domain candidate
    :param user: user object
    :param billing_account: optional parameter to limit available domains to within an enterprise account
    :return: list of domain names available to link as downstream projects
    """
    if domain_has_privilege(domain_name, RELEASE_MANAGEMENT):
        return get_available_upstream_domains_for_account(domain_name, user, billing_account)
    elif toggles.LINKED_DOMAINS.enabled(domain_name):
        return get_available_upstream_domains_for_user(domain_name, user)

    return []


def get_available_upstream_domains_for_account(domain_name, user, account):
    """
    :param domain_name: desired downstream domain
    :param user: couch user object
    :param account: billing account to grab domains from
    :return: list of domain names that are active upstream domains within the account
    """
    domains_in_account = account.get_domains() if account else []
    return list({d for d in domains_in_account if is_available_upstream_domain(d.name, domain_name, user)})


def get_available_upstream_domains_for_user(domain_name, user):
    domains_for_user = [d.name for d in Domain.active_for_user(user)]
    return list({d for d in domains_for_user
                 if is_available_upstream_domain(d.name, domain_name, user, should_enforce_admin=False)})


def get_accessible_downstream_domains(upstream_domain_name, user):
    """
    Returns a list of domain names that actively linked downstream of the provided upstream domain
    NOTE: if the RELEASE_MANAGEMENT privilege is enabled, ensure user has admin access
    """
    downstream_domains = [d.linked_domain for d in get_linked_domains(upstream_domain_name)]
    if domain_has_privilege(upstream_domain_name, RELEASE_MANAGEMENT):
        return [domain for domain in downstream_domains
                if user_has_admin_access_in_all_domains(user, [upstream_domain_name, domain])]
    return downstream_domains
