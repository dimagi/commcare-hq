from corehq.apps.domain.models import Domain

"""
Hacks for PSI that should eventually be removed
"""

def is_psi_domain(domain):
    if isinstance(domain, Domain):
        domain = domain.name
    # we can eventually make this explicit but for now this should be sufficient
    return (domain or '').startswith("psi-")
