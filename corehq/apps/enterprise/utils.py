from corehq.apps.enterprise.models import EnterprisePermissions


def get_enterprise_domains(domain):
    """Return list containing input domain and source domain for that input domain."""
    domain_list = [domain]
    config = EnterprisePermissions.get_by_domain(domain)
    if config.is_enabled and domain in config.domains:
        domain_list.append(config.source_domain)
    return domain_list
