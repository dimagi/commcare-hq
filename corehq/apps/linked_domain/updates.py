from functools import partial

from django.utils.translation import ugettext as _

from toggle.shortcuts import set_toggle

from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchQueryAddition,
)
from corehq.apps.custom_data_fields.models import (
    CustomDataField,
    CustomDataFieldsDefinition,
)
from corehq.apps.fixtures.dbaccessors import (
    delete_fixture_items_for_data_type,
    get_fixture_data_type_by_tag,
)
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.fixtures.upload.run_upload import clear_fixture_quickcache
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.linked_domain.const import (
    MODEL_CASE_SEARCH,
    MODEL_FIXTURE,
    MODEL_FLAGS,
    MODEL_LOCATION_DATA,
    MODEL_PRODUCT_DATA,
    MODEL_USER_DATA,
    MODEL_REPORT,
    MODEL_ROLES,
)
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.linked_domain.local_accessors import \
    get_custom_data_models as local_custom_data_models
from corehq.apps.linked_domain.local_accessors import \
    get_fixture as local_fixtures
from corehq.apps.linked_domain.local_accessors import \
    get_toggles_previews as local_toggles_previews
from corehq.apps.linked_domain.local_accessors import \
    get_user_roles as local_get_user_roles
from corehq.apps.linked_domain.remote_accessors import \
    get_case_search_config as remote_get_case_search_config
from corehq.apps.linked_domain.remote_accessors import \
    get_custom_data_models as remote_custom_data_models
from corehq.apps.linked_domain.remote_accessors import \
    get_fixture as remote_fixtures
from corehq.apps.linked_domain.remote_accessors import \
    get_toggles_previews as remote_toggles_previews
from corehq.apps.linked_domain.remote_accessors import \
    get_user_roles as remote_get_user_roles
from corehq.apps.linked_domain.ucr import update_linked_ucr
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
        MODEL_FIXTURE: update_fixture,
        MODEL_FLAGS: update_toggles_previews,
        MODEL_ROLES: update_user_roles,
        MODEL_LOCATION_DATA: partial(update_custom_data_models, limit_types=[LocationFieldsView.field_type]),
        MODEL_PRODUCT_DATA: partial(update_custom_data_models, limit_types=[ProductFieldsView.field_type]),
        MODEL_USER_DATA: partial(update_custom_data_models, limit_types=[UserFieldsView.field_type]),
        MODEL_CASE_SEARCH: update_case_search_config,
        MODEL_REPORT: update_linked_ucr,
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


def update_fixture(domain_link, tag):
    if domain_link.is_remote:
        master_results = remote_fixtures(domain_link, tag)
    else:
        master_results = local_fixtures(domain_link.master_domain, tag)

    master_data_type = master_results["data_type"]
    if not master_data_type.is_global:
        raise UnsupportedActionError(_("Found non-global lookup table '{}'.").format(master_data_type.tag))

    # Update data type
    master_data_type = master_data_type.to_json()
    del master_data_type["_id"]
    del master_data_type["_rev"]

    linked_data_type = get_fixture_data_type_by_tag(domain_link.linked_domain, master_data_type["tag"])
    if linked_data_type:
        linked_data_type = linked_data_type.to_json()
    else:
        linked_data_type = {}
    linked_data_type.update(master_data_type)
    linked_data_type["domain"] = domain_link.linked_domain
    linked_data_type = FixtureDataType.wrap(linked_data_type)
    linked_data_type.save()
    clear_fixture_quickcache(domain_link.linked_domain, [linked_data_type])

    # Re-create relevant data items
    delete_fixture_items_for_data_type(domain_link.linked_domain, linked_data_type._id)
    for master_item in master_results["data_items"]:
        doc = master_item.to_json()
        del doc["_id"]
        del doc["_rev"]
        doc["domain"] = domain_link.linked_domain
        doc["data_type_id"] = linked_data_type._id
        FixtureDataItem.wrap(doc).save()

    clear_fixture_cache(domain_link.linked_domain)


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
