from corehq.apps.linked_domain.local_accessors import get_toggles_previews as local_toggles_previews
from corehq.apps.linked_domain.remote_accessors import get_toggles_previews as remote_toggles_previews
from corehq.toggles import NAMESPACE_DOMAIN
from toggle.shortcuts import set_toggle


def update_toggles_previews(domain_link):
    if domain_link.is_remote:
        master_results = remote_toggles_previews(domain_link)
    else:
        master_results = local_toggles_previews(domain_link.master_domain)

    master_toggles = set(master_results['toggles'])
    master_previews = set(master_results['previews'])

    local_results = local_toggles_previews(domain_link.linked_domain)
    local_toggles = set(local_results['toggles'])
    local_previews = set(local_results['previews'])

    def _set_toggles(collection, enabled):
        for slug in collection:
            set_toggle(slug, domain_link.linked_domain, enabled, NAMESPACE_DOMAIN)

    _set_toggles(master_toggles - local_toggles, True)
    _set_toggles(master_previews - local_previews, True)
