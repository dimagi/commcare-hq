
from functools import partial

from toggle.shortcuts import set_toggle

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import LinkedApplication
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchQueryAddition,
)
from corehq.apps.custom_data_fields.models import (
    CustomDataField,
    CustomDataFieldsDefinition,
)
from corehq.apps.domain.dbaccessors import get_docs_in_domain_by_class
from corehq.apps.linked_domain.const import (
    MODEL_CASE_SEARCH,
    MODEL_FLAGS,
    MODEL_LOCATION_DATA,
    MODEL_PRODUCT_DATA,
    MODEL_USER_DATA,
    MODELS_ROLES,
)
from corehq.apps.linked_domain.local_accessors import \
    get_custom_data_models as local_custom_data_models
from corehq.apps.linked_domain.local_accessors import \
    get_toggles_previews as local_toggles_previews
from corehq.apps.linked_domain.local_accessors import \
    get_user_roles as local_get_user_roles
from corehq.apps.linked_domain.remote_accessors import \
    get_case_search_config as remote_get_case_search_config
from corehq.apps.linked_domain.remote_accessors import \
    get_custom_data_models as remote_custom_data_models
from corehq.apps.linked_domain.remote_accessors import \
    get_toggles_previews as remote_toggles_previews
from corehq.apps.linked_domain.remote_accessors import \
    get_user_roles as remote_get_user_roles
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.products.views import ProductFieldsView
from corehq.apps.userreports.util import (
    get_static_report_mapping,
    get_ucr_class_name,
)
from corehq.apps.users.models import UserRole
from corehq.apps.users.views.mobile import UserFieldsView
from corehq.toggles import NAMESPACE_DOMAIN


def update_model_type(domain_link, model_type, model_detail=None):
    update_fn = {
        MODEL_FLAGS: update_toggles_previews,
        MODELS_ROLES: update_user_roles,
        MODEL_LOCATION_DATA: partial(update_custom_data_models, limit_types=[LocationFieldsView.field_type]),
        MODEL_PRODUCT_DATA: partial(update_custom_data_models, limit_types=[ProductFieldsView.field_type]),
        MODEL_USER_DATA: partial(update_custom_data_models, limit_types=[UserFieldsView.field_type]),
        MODEL_CASE_SEARCH: update_case_search_config,
    }.get(model_type)

    kwargs = model_detail or {}
    update_fn(domain_link, **kwargs)


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


def update_custom_data_models(domain_link, limit_types=None):
    if domain_link.is_remote:
        master_results = remote_custom_data_models(domain_link, limit_types)
    else:
        master_results = local_custom_data_models(domain_link.master_domain, limit_types)

    for field_type, field_definitions in master_results.items():
        model = CustomDataFieldsDefinition.get_or_create(domain_link.linked_domain, field_type)
        model.fields = [CustomDataField.wrap(field_def) for field_def in field_definitions]
        model.save()


def update_user_roles(domain_link):
    if domain_link.is_remote:
        master_results = remote_get_user_roles(domain_link)
    else:
        master_results = local_get_user_roles(domain_link.master_domain)

    _convert_reports_permissions(domain_link, master_results)

    local_roles = UserRole.view(
        'users/roles_by_domain',
        startkey=[domain_link.linked_domain],
        endkey=[domain_link.linked_domain, {}],
        include_docs=True,
        reduce=False,
    )
    local_roles_by_name = {role.name: role for role in local_roles}
    for role_def in master_results:
        role = local_roles_by_name.get(role_def['name'])
        if role:
            role_json = role.to_json()
        else:
            role_json = {'domain': domain_link.linked_domain}

        role_json.update(role_def)
        UserRole.wrap(role_json).save()


def update_case_search_config(domain_link):
    if domain_link.is_remote:
        remote_properties = remote_get_case_search_config(domain_link)
        case_search_config = remote_properties['config']
        if not case_search_config:
            return
        query_addition = remote_properties['addition']
    else:
        try:
            case_search_config = CaseSearchConfig.objects.get(domain=domain_link.master_domain).to_json()
        except CaseSearchConfig.DoesNotExist:
            return

        try:
            query_addition = CaseSearchQueryAddition.objects.get(domain=domain_link.master_domain).to_json()
        except CaseSearchQueryAddition.DoesNotExist:
            query_addition = None

    CaseSearchConfig.create_model_and_index_from_json(domain_link.linked_domain, case_search_config)

    if query_addition:
        CaseSearchQueryAddition.create_from_json(domain_link.linked_domain, query_addition)


def _convert_reports_permissions(domain_link, master_results):
    """Mutates the master result docs to convert dynamic report permissions.
    """
    report_map = get_static_report_mapping(domain_link.master_domain, domain_link.linked_domain)
    for role_def in master_results:
        new_report_perms = [
            perm for perm in role_def['permissions']['view_report_list']
            if 'DynamicReport' not in perm
        ]

        for master_id, linked_id in report_map.items():
            master_report_perm = get_ucr_class_name(master_id)
            if master_report_perm in role_def['permissions']['view_report_list']:
                new_report_perms.append(get_ucr_class_name(linked_id))

        role_def['permissions']['view_report_list'] = new_report_perms
