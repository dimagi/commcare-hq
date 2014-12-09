from custom.ewsghana.models import EWSGhanaConfig


def domain_has_ews_enabled(domain):
    config = EWSGhanaConfig.for_domain(domain)
    return config and config.enabled
