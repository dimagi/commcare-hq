from custom.ewsghana.models import EWSGhanaConfig


def domain_has_ews_enabled(domain):
    config = EWSGhanaConfig.for_domain(domain)
    if config and config.enabled:
        return True
    else:
        return False
