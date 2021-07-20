from copy import copy
from corehq.apps.reports.models import TableauVisualization, TableauServer
from functools import partial

from django.utils.translation import ugettext as _

from toggle.shortcuts import set_toggle

from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.data_dictionary.models import (
    CaseType,
    CaseProperty
)
from corehq.apps.integration.models import (
    DialerSettings,
    GaenOtpServerSettings,
    HmacCalloutSettings,
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
    MODEL_KEYWORD,
    MODEL_LOCATION_DATA,
    MODEL_PRODUCT_DATA,
    MODEL_USER_DATA,
    MODEL_REPORT,
    MODEL_ROLES,
    MODEL_DATA_DICTIONARY,
    MODEL_DIALER_SETTINGS,
    MODEL_OTP_SETTINGS,
    MODEL_HMAC_CALLOUT_SETTINGS,
    MODEL_TABLEAU_SERVER_AND_VISUALIZATIONS,
)
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.linked_domain.local_accessors import \
    get_custom_data_models as local_custom_data_models
from corehq.apps.linked_domain.local_accessors import \
    get_fixture as local_fixture
from corehq.apps.linked_domain.local_accessors import \
    get_toggles_previews as local_toggles_previews
from corehq.apps.linked_domain.local_accessors import \
    get_user_roles as local_get_user_roles
from corehq.apps.linked_domain.local_accessors import \
    get_data_dictionary as local_get_data_dictionary
from corehq.apps.linked_domain.local_accessors import \
    get_tableau_server_and_visualizations as local_get_tableau_server_and_visualizations
from corehq.apps.linked_domain.local_accessors import \
    get_dialer_settings as local_get_dialer_settings
from corehq.apps.linked_domain.local_accessors import \
    get_otp_settings as local_get_otp_settings
from corehq.apps.linked_domain.local_accessors import \
    get_hmac_callout_settings as local_get_hmac_callout_settings
from corehq.apps.linked_domain.remote_accessors import \
    get_case_search_config as remote_get_case_search_config
from corehq.apps.linked_domain.remote_accessors import \
    get_custom_data_models as remote_custom_data_models
from corehq.apps.linked_domain.remote_accessors import \
    get_fixture as remote_fixture
from corehq.apps.linked_domain.remote_accessors import \
    get_toggles_previews as remote_toggles_previews
from corehq.apps.linked_domain.remote_accessors import \
    get_user_roles as remote_get_user_roles
from corehq.apps.linked_domain.remote_accessors import \
    get_data_dictionary as remote_get_data_dictionary
from corehq.apps.linked_domain.remote_accessors import \
    get_tableau_server_and_visualizations as remote_get_tableau_server_and_visualizations
from corehq.apps.linked_domain.remote_accessors import \
    get_dialer_settings as remote_get_dialer_settings
from corehq.apps.linked_domain.remote_accessors import \
    get_otp_settings as remote_get_otp_settings
from corehq.apps.linked_domain.remote_accessors import \
    get_hmac_callout_settings as remote_get_hmac_callout_settings
from corehq.apps.linked_domain.ucr import update_linked_ucr
from corehq.apps.linked_domain.keywords import update_keyword
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.products.views import ProductFieldsView
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.util import (
    get_static_report_mapping,
    get_ucr_class_name,
)
from corehq.apps.users.models import SQLUserRole, Permissions
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
        MODEL_DATA_DICTIONARY: update_data_dictionary,
        MODEL_DIALER_SETTINGS: update_dialer_settings,
        MODEL_OTP_SETTINGS: update_otp_settings,
        MODEL_HMAC_CALLOUT_SETTINGS: update_hmac_callout_settings,
        MODEL_KEYWORD: update_keyword,
        MODEL_TABLEAU_SERVER_AND_VISUALIZATIONS: update_tableau_server_and_visualizations,
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

    for field_type, data in master_results.items():
        field_definitions = data.get('fields', [])
        model = CustomDataFieldsDefinition.get_or_create(domain_link.linked_domain, field_type)
        model.set_fields([
            Field(
                slug=field_def['slug'],
                is_required=field_def['is_required'],
                label=field_def['label'],
                choices=field_def['choices'],
                regex=field_def['regex'],
                regex_msg=field_def['regex_msg'],
            ) for field_def in field_definitions
        ])
        model.save()

        old_profiles = {profile.name: profile for profile in model.get_profiles()}
        for profile in data.get('profiles'):
            old_profile = old_profiles.get(profile['name'], None)
            if old_profile:
                old_profile.fields = profile['fields']
                old_profile.save()
            else:
                CustomDataFieldsProfile(
                    name=profile['name'],
                    definition=model,
                    fields=profile['fields'],
                ).save()


def update_fixture(domain_link, tag):
    if domain_link.is_remote:
        master_results = remote_fixture(domain_link, tag)
    else:
        master_results = local_fixture(domain_link.master_domain, tag)

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

    local_roles = SQLUserRole.objects.get_by_domain(domain_link.linked_domain, include_archived=True)
    local_roles_by_name = {}
    local_roles_by_upstream_id = {}
    for role in local_roles:
        local_roles_by_name[role.name] = role
        if role.upstream_id:
            local_roles_by_upstream_id[role.upstream_id] = role

    # Update downstream roles based on upstream roles
    for role_def in master_results:
        role = local_roles_by_upstream_id.get(role_def['_id']) or local_roles_by_name.get(role_def['name'])
        if not role:
            role = SQLUserRole(domain=domain_link.linked_domain)
        local_roles_by_upstream_id[role_def['_id']] = role
        role.upstream_id = role_def['_id']

        role.name = role_def["name"]
        role.default_landing_page = role_def["default_landing_page"]
        role.is_non_admin_editable = role_def["is_non_admin_editable"]
        role.save()

        permissions = Permissions.wrap(role_def["permissions"])
        role.set_permissions(permissions.to_list())

    # Update assignable_by ids - must be done after main update to guarantee all local roles have ids
    for role_def in master_results:
        local_role = local_roles_by_upstream_id[role_def['_id']]
        assignable_by = []
        if role_def["assignable_by"]:
            assignable_by = [
                local_roles_by_upstream_id[role_id].id
                for role_id in role_def["assignable_by"]
            ]
        local_role.set_assignable_by(assignable_by)


def update_case_search_config(domain_link):
    if domain_link.is_remote:
        remote_properties = remote_get_case_search_config(domain_link)
        case_search_config = remote_properties['config']
        if not case_search_config:
            return
    else:
        try:
            case_search_config = CaseSearchConfig.objects.get(domain=domain_link.master_domain).to_json()
        except CaseSearchConfig.DoesNotExist:
            return

    CaseSearchConfig.create_model_and_index_from_json(domain_link.linked_domain, case_search_config)


def update_data_dictionary(domain_link):
    if domain_link.is_remote:
        master_results = remote_get_data_dictionary(domain_link)
    else:
        master_results = local_get_data_dictionary(domain_link.master_domain)

    # Start from an empty set of CaseTypes and CaseProperties in the linked domain.
    CaseType.objects.filter(domain=domain_link.linked_domain).delete()

    # Create CaseType and CaseProperty as necessary
    for case_type_name, case_type_desc in master_results.items():
        case_type_obj = CaseType.get_or_create(domain_link.linked_domain, case_type_name)
        case_type_obj.description = case_type_desc['description']
        case_type_obj.fully_generated = case_type_desc['fully_generated']
        case_type_obj.save()

        for case_property_name, case_property_desc in case_type_desc['properties'].items():
            case_property_obj = CaseProperty.get_or_create(case_property_name,
                                                           case_type_obj.name,
                                                           domain_link.linked_domain)
            case_property_obj.description = case_property_desc['description']
            case_property_obj.deprecated = case_property_desc['deprecated']
            case_property_obj.data_type = case_property_desc['data_type']
            case_property_obj.group = case_property_desc['group']
            case_property_obj.save()


def update_tableau_server_and_visualizations(domain_link):
    if domain_link.is_remote:
        master_results = remote_get_tableau_server_and_visualizations(domain_link)
    else:
        master_results = local_get_tableau_server_and_visualizations(domain_link.master_domain)

    server_model, created = TableauServer.objects.get_or_create(domain=domain_link.linked_domain)

    server_model.domain = domain_link.linked_domain
    server_model.server_type = master_results["server"]['server_type']
    server_model.server_name = master_results["server"]['server_name']
    server_model.validate_hostname = master_results["server"]['validate_hostname']
    server_model.target_site = master_results["server"]['target_site']
    server_model.domain_username = master_results["server"]['domain_username']
    server_model.allow_domain_username_override = master_results["server"]['allow_domain_username_override']
    server_model.save()

    visualization_models = TableauVisualization.objects.all().filter(
        domain=domain_link.linked_domain).order_by('pk')

    if not len(visualization_models):
        vis = TableauVisualization(domain=domain_link.linked_domain, server=server_model)
        vis.save()
    else:
        for i in range(len(visualization_models)):
            visualization_models[i].domain = domain_link.linked_domain
            visualization_models[i].server = master_results['visualizations'][i]['server']
            visualization_models[i].view_url = master_results['visualizations'][i]['view_url']
            visualization_models[i].save()

def update_dialer_settings(domain_link):
    if domain_link.is_remote:
        master_results = remote_get_dialer_settings(domain_link)
    else:
        master_results = local_get_dialer_settings(domain_link.master_domain)

    model, created = DialerSettings.objects.get_or_create(domain=domain_link.linked_domain)

    model.domain = domain_link.linked_domain
    model.aws_instance_id = master_results['aws_instance_id']
    model.is_enabled = master_results['is_enabled']
    model.dialer_page_header = master_results['dialer_page_header']
    model.dialer_page_subheader = master_results['dialer_page_subheader']
    model.save()


def update_otp_settings(domain_link):
    if domain_link.is_remote:
        master_results = remote_get_otp_settings(domain_link)
    else:
        master_results = local_get_otp_settings(domain_link.master_domain)

    model, created = GaenOtpServerSettings.objects.get_or_create(domain=domain_link.linked_domain)

    model.domain = domain_link.linked_domain
    model.is_enabled = master_results['is_enabled']
    model.server_url = master_results['server_url']
    model.auth_token = master_results['auth_token']
    model.save()


def update_hmac_callout_settings(domain_link):
    if domain_link.is_remote:
        master_results = remote_get_hmac_callout_settings(domain_link)
    else:
        master_results = local_get_hmac_callout_settings(domain_link.master_domain)

    model, created = HmacCalloutSettings.objects.get_or_create(domain=domain_link.linked_domain)

    model.domain = domain_link.linked_domain
    model.destination_url = master_results['destination_url']
    model.is_enabled = master_results['is_enabled']
    model.api_key = master_results['api_key']
    model.api_secret = master_results['api_secret']
    model.save()


def _convert_reports_permissions(domain_link, master_results):
    """Mutates the master result docs to convert dynamic report permissions.
    """
    report_map = get_static_report_mapping(domain_link.master_domain, domain_link.linked_domain)
    report_map.update({
        c.report_meta.master_id: c._id
        for c in get_report_configs_for_domain(domain_link.linked_domain)
    })

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
