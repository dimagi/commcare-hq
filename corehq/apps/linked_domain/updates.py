from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.custom_data_fields.models import CustomDataField
from corehq.apps.linked_domain.local_accessors import (
    get_toggles_previews as local_toggles_previews,
    get_custom_data_models as local_custom_data_models,
)
from corehq.apps.linked_domain.remote_accessors import (
    get_toggles_previews as remote_toggles_previews,
    get_custom_data_models as remote_custom_data_models,
)
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


def update_custom_data_models(domain_link):
    if domain_link.is_remote:
        master_results = remote_custom_data_models(domain_link)
    else:
        master_results = local_custom_data_models(domain_link.master_domain)

    for field_type, field_definitions in master_results.items():
        model = CustomDataFieldsDefinition.get_or_create(domain_link.linked_domain, field_type)
        model.fields = [CustomDataField.wrap(field_def) for field_def in field_definitions]
        model.save()
