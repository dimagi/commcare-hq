from corehq.apps.linked_domain.ucr_expressions import update_linked_ucr_expression
from corehq.apps.reports.models import TableauVisualization, TableauServer
from functools import partial

from django.utils.translation import gettext as _
from django.db import transaction

from dimagi.utils.chunked import chunked

from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule, CaseRuleAction, CaseRuleCriteria,
    ClosedParentDefinition, CustomActionDefinition,
    CustomMatchDefinition, MatchPropertyDefinition, UpdateCaseDefinition,
    LocationFilterDefinition,
)
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.data_dictionary.models import (
    CasePropertyGroup,
    CaseType,
    CaseProperty
)
from corehq.apps.integration.models import (
    DialerSettings,
    GaenOtpServerSettings,
    HmacCalloutSettings,
)
from corehq.apps.fixtures.models import LookupTable, LookupTableRow
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.linked_domain.const import (
    MODEL_AUTO_UPDATE_RULE,
    MODEL_AUTO_UPDATE_RULES,
    MODEL_CASE_SEARCH,
    MODEL_FIXTURE,
    MODEL_FLAGS,
    MODEL_KEYWORD,
    MODEL_LOCATION_DATA,
    MODEL_PREVIEWS,
    MODEL_PRODUCT_DATA,
    MODEL_UCR_EXPRESSION,
    MODEL_USER_DATA,
    MODEL_REPORT,
    MODEL_ROLES,
    MODEL_DATA_DICTIONARY,
    MODEL_DIALER_SETTINGS,
    MODEL_OTP_SETTINGS,
    MODEL_HMAC_CALLOUT_SETTINGS,
    MODEL_TABLEAU_SERVER_AND_VISUALIZATIONS,
)
from corehq.apps.linked_domain.exceptions import DomainLinkError, UnsupportedActionError
from corehq.apps.linked_domain.local_accessors import \
    get_enabled_previews as local_enabled_previews
from corehq.apps.linked_domain.local_accessors import \
    get_enabled_toggles as local_enabled_toggles
from corehq.apps.linked_domain.local_accessors import \
    get_custom_data_models as local_custom_data_models
from corehq.apps.linked_domain.local_accessors import \
    get_fixture as local_fixture
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
from corehq.apps.linked_domain.local_accessors import \
    get_auto_update_rules as local_get_auto_update_rules
from corehq.apps.linked_domain.local_accessors import \
    get_auto_update_rule as local_get_auto_update_rule
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
from corehq.apps.linked_domain.remote_accessors import \
    get_auto_update_rules as remote_get_auto_update_rules
from corehq.apps.linked_domain.ucr import update_linked_ucr
from corehq.apps.linked_domain.keywords import update_keyword
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.products.views import ProductFieldsView
from corehq.apps.userreports.dbaccessors import get_report_and_registry_report_configs_for_domain
from corehq.apps.userreports.util import (
    get_static_report_mapping,
    get_ucr_class_name,
)
from corehq.apps.users.models import UserRole, HqPermissions
from corehq.apps.users.views.mobile import UserFieldsView
from corehq.toggles import NAMESPACE_DOMAIN, EMBEDDED_TABLEAU
from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE
from corehq.toggles.shortcuts import set_toggle

from corehq.apps.users.role_utils import UserRolePresets


def update_model_type(domain_link, model_type, model_detail=None, is_pull=False, overwrite=False):
    update_fn = {
        MODEL_AUTO_UPDATE_RULE: update_auto_update_rule,
        MODEL_AUTO_UPDATE_RULES: update_auto_update_rules,
        MODEL_FIXTURE: update_fixture,
        MODEL_FLAGS: update_toggles,
        MODEL_PREVIEWS: update_previews,
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
        MODEL_UCR_EXPRESSION: update_linked_ucr_expression,
    }.get(model_type)

    kwargs = {}
    if model_detail:
        kwargs.update(model_detail)
    kwargs['is_pull'] = is_pull
    kwargs['overwrite'] = overwrite

    update_fn(domain_link, **kwargs)


def update_toggles(domain_link, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        upstream_results = remote_toggles_previews(domain_link)
        upstream_toggles = set(upstream_results['toggles'])
    else:
        upstream_toggles = set(local_enabled_toggles(domain_link.master_domain))

    downstream_toggles = set(local_enabled_toggles(domain_link.linked_domain))

    def _set_toggles(collection, enabled):
        for slug in collection:
            set_toggle(slug, domain_link.linked_domain, enabled, NAMESPACE_DOMAIN)

    # enable downstream toggles that are enabled upstream
    _set_toggles(upstream_toggles - downstream_toggles, True)


def update_previews(domain_link, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        upstream_results = remote_toggles_previews(domain_link)
        upstream_previews = set(upstream_results['previews'])
    else:
        upstream_previews = set(local_enabled_previews(domain_link.master_domain))

    downstream_previews = set(local_enabled_previews(domain_link.linked_domain))

    def _set_toggles(collection, enabled):
        for slug in collection:
            set_toggle(slug, domain_link.linked_domain, enabled, NAMESPACE_DOMAIN)

    # enable downstream previews that are enabled upstream
    _set_toggles(upstream_previews - downstream_previews, True)


def update_custom_data_models(domain_link, limit_types=None, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        upstream_results = remote_custom_data_models(domain_link, limit_types)
    else:
        upstream_results = local_custom_data_models(domain_link.master_domain, limit_types)

    update_custom_data_models_impl(upstream_results, domain_link.linked_domain, is_pull, overwrite)


def update_custom_data_models_impl(upstream_results, downstream_domain, is_pull=False, overwrite=False):
    for field_type, data in upstream_results.items():
        upstream_field_definitions = data.get('fields', [])
        model = CustomDataFieldsDefinition.get_or_create(downstream_domain, field_type)
        merged_fields = merge_fields(model.get_fields(), upstream_field_definitions, field_type,
                                     is_pull=is_pull, overwrite=overwrite)
        model.set_fields(merged_fields)
        model.save()

        if field_type == CUSTOM_USER_DATA_FIELD_TYPE:
            # Profiles are only currently used by custom user data
            update_profiles(model, data.get('profiles', []), is_pull, overwrite)


def merge_fields(downstream_fields, upstream_fields, field_type, is_pull=False, overwrite=False):
    managed_fields = [create_local_field(field_def) for field_def in upstream_fields]
    local_fields = [field for field in downstream_fields if not field.upstream_id]

    local_slugs = [field.slug for field in local_fields]
    conflicting_slugs = [field.slug for field in managed_fields if field.slug in local_slugs]
    if conflicting_slugs and not overwrite:
        field_name_map = {
            CUSTOM_USER_DATA_FIELD_TYPE: 'Custom User Data Fields',
            LocationFieldsView.field_type: 'Custom Location Data Fields'
        }
        field_name = field_name_map.get(field_type, 'Custom Data Fields')

        property_name_map = {
            CUSTOM_USER_DATA_FIELD_TYPE: 'User Property',
            LocationFieldsView.field_type: 'Location Property',
        }
        property_name = property_name_map.get(field_type, 'Custom Property')

        quoted_conflicts = ', '.join(['"{}"'.format(name) for name in conflicting_slugs])

        action = _('sync') if is_pull else _('push')
        overwrite_action = _('Sync & Overwrite') if is_pull else _('Push & Overwrite')

        raise DomainLinkError(_(
            'Failed to {sync_action} the following {field_name} due to matching (same {property_name})'
            ' unlinked {field_name} in this downstream project space: {conflicts}.'
            ' Please edit the {field_name} to resolve the matching or click "{overwrite_btn}"'
            ' to overwrite and link the matching ones.').format(
                sync_action=action,
                field_name=field_name,
                property_name=property_name,
                conflicts=quoted_conflicts,
                overwrite_btn=overwrite_action
        ))

    unique_local_fields = [field for field in local_fields if field.slug not in conflicting_slugs]

    return managed_fields + unique_local_fields


# TODO: Make this whole thing a transaction
def update_profiles(definition, upstream_profiles, is_pull=False, overwrite=False):
    downstream_profiles = definition.get_profiles()
    unsynced_profile_names = [profile.name for profile in downstream_profiles if not profile.upstream_id]
    conflicting_profile_names = [
        profile['name'] for profile in upstream_profiles if profile['name'] in unsynced_profile_names
    ]
    if conflicting_profile_names:
        if not overwrite:
            action = _('sync') if is_pull else _('push')
            overwrite_action = _('Sync & Overwrite') if is_pull else _('Push & Overwrite')
            quoted_conflicts = ', '.join(['"{}"'.format(name) for name in conflicting_profile_names])
            raise DomainLinkError(_(
                'Failed to {sync_action} the following Custom User Data Fields Profiles due to matching'
                ' (same User Profile) unlinked Custom User Data Fields Profiles in this downstream project space:'
                ' {conflicts}. Please edit the Custom User Data Fields Profiles to resolve the matching or'
                ' click "{overwrite_btn}" to overwrite and link the matching ones.').format(
                    sync_action=action,
                    conflicts=quoted_conflicts,
                    overwrite_btn=overwrite_action
            ))
        else:
            # If none of these conflicting profiles have assigned users, then delete them
            # so that the upstream profiles can overwrite them
            # TODO: Raise an error message if the profiles have assigned users
            conflicting_profiles = [
                profile for profile in downstream_profiles if profile.name in conflicting_profile_names]
            profiles_in_use = [profile.name for profile in conflicting_profiles if profile.has_users_assigned]
            if profiles_in_use:
                raise DomainLinkError(_(
                    'Cannot overwrite profiles, as the following profiles are still in use: {profiles}').format(
                        profiles=", ".join(profiles_in_use))
                )
            for profile in conflicting_profiles:
                profile.delete()

    existing_managed_profiles = {profile.name: profile for profile in downstream_profiles if profile.upstream_id}

    for profile in upstream_profiles:
        existing_profile = existing_managed_profiles.pop(profile['name'], None)
        if existing_profile:
            existing_profile.fields = profile['fields']
            existing_profile.save()
        else:
            new_profile = create_synced_profile(profile, definition)
            new_profile.save()

    # What is left in existing_managed_profiles must be deleted
    for profile in existing_managed_profiles.values():
        # do not delete profiles that are in use, as it would be disruptive
        # it's possible that it might be better to create an error message
        #  pointing to the specific users that are using the profile,
        #  and allow the operator to either unassign that profile from those users,
        #  or make the profile local to the domain
        if not profile.has_users_assigned:
            profile.delete()

    # Likely need to check for validity after the merge;
    # A synced field could have been removed, and local profiles may still depend on that synced field


def create_local_field(upstream_field_definition):
    return Field(
        slug=upstream_field_definition['slug'],
        is_required=upstream_field_definition['is_required'],
        label=upstream_field_definition['label'],
        choices=upstream_field_definition['choices'],
        regex=upstream_field_definition['regex'],
        regex_msg=upstream_field_definition['regex_msg'],
        upstream_id=upstream_field_definition['id'],
    )


def create_synced_profile(upstream_profile, definition):
    return CustomDataFieldsProfile(
        name=upstream_profile['name'],
        definition=definition,
        fields=upstream_profile['fields'],
        upstream_id=upstream_profile['id'],
    )


def update_fixture(domain_link, tag, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        # FIXME Gets a requests.request(...) response object, which does
        # not support the operations below. It has never worked.
        master_results = remote_fixture(domain_link, tag)
    else:
        master_results = local_fixture(domain_link.master_domain, tag)

    master_data_type = master_results["data_type"]
    if not master_data_type.is_global:
        raise UnsupportedActionError(_("Found non-global lookup table '{table}'.").format(
            table=master_data_type.tag))

    # Update data type
    try:
        linked_data_type = LookupTable.objects.by_domain_tag(
            domain_link.linked_domain, master_data_type.tag)

        if not linked_data_type.is_synced and not overwrite:
            # if local data exists, but it was not created through syncing, reject the sync request
            action = _('sync') if is_pull else _('push')
            overwrite_action = _('Sync & Overwrite') if is_pull else _('Push & Overwrite')
            raise UnsupportedActionError(
                _('Failed to {sync_action} Lookup Table "{table}" due to matching (same Table ID) unlinked Lookup'
                  ' Table in the downstream project space. Please edit the Lookup Table to resolve the matching'
                  ' or click "{overwrite_btn}" to overwrite and link them.')
                .format(sync_action=action, table=linked_data_type.tag, overwrite_btn=overwrite_action)
            )
        is_existing_table = True
    except LookupTable.DoesNotExist:
        linked_data_type = LookupTable(domain=domain_link.linked_domain)
        is_existing_table = False

    for field in LookupTable._meta.fields:
        if field.attname not in ["id", "domain"]:
            value = getattr(master_data_type, field.attname)
            setattr(linked_data_type, field.attname, value)
    linked_data_type.is_synced = True
    linked_data_type.save()

    # Re-create relevant data items
    if is_existing_table:
        LookupTableRow.objects.filter(
            domain=domain_link.linked_domain,
            table_id=linked_data_type.id
        ).delete()
    ignore_fields = {"id", "domain", "table", "table_id"}
    row_fields = [field.attname
        for field in LookupTableRow._meta.fields
        if field.attname not in ignore_fields]
    rows = (LookupTableRow(
        domain=domain_link.linked_domain,
        table_id=linked_data_type.id,
        **{f: getattr(master_item, f) for f in row_fields}
    ) for master_item in master_results["data_items"])
    for chunk in chunked(rows, 1000, list):
        LookupTableRow.objects.bulk_create(chunk)

    clear_fixture_cache(domain_link.linked_domain)


#TODO: Limit the scope of this atomicity. Ideally, we fetch and prep the data prior to entering the atomic block
@transaction.atomic
def update_user_roles(domain_link, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        upstream_roles = remote_get_user_roles(domain_link)
    else:
        upstream_roles = local_get_user_roles(domain_link.master_domain)

    _convert_reports_permissions(domain_link, upstream_roles)

    downstream_roles = UserRole.objects.get_by_domain(domain_link.linked_domain, include_archived=True)

    downstream_roles_by_name = {}
    downstream_roles_by_upstream_id = {}
    for role in downstream_roles:
        downstream_roles_by_name[role.name] = role
        if role.upstream_id:
            downstream_roles_by_upstream_id[role.upstream_id] = role

    is_embedded_tableau_enabled = EMBEDDED_TABLEAU.enabled(domain_link.linked_domain)
    if is_embedded_tableau_enabled:
        visualizations_for_linked_domain = TableauVisualization.objects.filter(
            domain=domain_link.linked_domain)
    failed_default_updates = []
    failed_custom_updates = []
    successful_updates = []

    # Update downstream roles based on upstream roles
    for upstream_role_def in upstream_roles:
        role, conflicting_role_name, is_default_role = _get_synced_role(
            upstream_role_def, domain_link.linked_domain, downstream_roles,
            downstream_roles_by_name, ignore_conflicts=overwrite)

        if conflicting_role_name:
            if is_default_role:
                failed_default_updates.append(conflicting_role_name)
            else:
                failed_custom_updates.append(conflicting_role_name)
            continue

        permissions = HqPermissions.wrap(upstream_role_def["permissions"])
        if is_embedded_tableau_enabled:
            permissions.view_tableau_list = _get_new_tableau_report_permissions(
                visualizations_for_linked_domain, permissions, role.permissions)
        role.save()
        role.set_permissions(permissions.to_list())
        successful_updates.append(upstream_role_def)
        downstream_roles_by_upstream_id[upstream_role_def['_id']] = role

    if failed_default_updates or failed_custom_updates:
        action = _('sync') if is_pull else _('push')
        overwrite_action = _('Sync & Overwrite') if is_pull else _('Push & Overwrite')
        error_messages = []
        if failed_default_updates:
            conflicting_names = ', '.join(['"{}"'.format(name) for name in failed_default_updates])
            error_messages.append(_(
                'Failed to {sync_action} the following default roles due to matching (same name but different'
                ' permissions) unlinked roles in this downstream project space: {conflicting_role_names}.'
                ' Please edit the roles to resolve the matching or click "{overwrite_btn}"'
                ' to overwrite and link the matching ones.'
            ).format(sync_action=action, conflicting_role_names=conflicting_names, overwrite_btn=overwrite_action))
        if failed_custom_updates:
            conflicting_names = ', '.join(['"{}"'.format(name) for name in failed_custom_updates])
            error_messages.append(_(
                'Failed to {sync_action} the following custom roles due to matching (same name) unlinked roles in'
                ' this downstream project space: {conflicting_role_names}. Please edit the roles to resolve the'
                ' matching or click "{overwrite_btn}" to overwrite and link the matching ones.'
            ).format(sync_action=action, conflicting_role_names=conflicting_names, overwrite_btn=overwrite_action))
        raise UnsupportedActionError('\n'.join(error_messages))

    # Update assignable_by ids - must be done after main update to guarantee all local roles have ids
    for upstream_role_def in successful_updates:
        downstream_role = downstream_roles_by_upstream_id[upstream_role_def['_id']]
        assignable_by = []
        if upstream_role_def["assignable_by"]:
            assignable_by = [
                downstream_roles_by_upstream_id[role_id].id
                for role_id in upstream_role_def["assignable_by"]
            ]
        downstream_role.set_assignable_by(assignable_by)


def _get_synced_role(upstream_role_def, downstream_domain, downstream_roles,
                     downstream_roles_by_name, ignore_conflicts):
    role, conflicting_role, is_default_role = _get_matching_downstream_role(upstream_role_def,
                                                           downstream_roles,
                                                           ignore_conflicts=ignore_conflicts)

    if conflicting_role and not ignore_conflicts:
        return (None, upstream_role_def['name'], is_default_role)

    if not role:
        role = UserRole(domain=downstream_domain)

    _copy_role_attributes(upstream_role_def, role)

    if conflicting_role:
        role.name = _get_next_free_name(role.name, downstream_roles_by_name)

    return (role, None, is_default_role)


def _get_next_free_name(initial_name, existing_names):
    next_index = 0
    name = initial_name
    while name in existing_names:
        next_index += 1
        name = f'{initial_name}({next_index})'

    return name


def _get_matching_downstream_role(upstream_role_json, downstream_roles, ignore_conflicts=False):
    matching_role = None
    conflicting_role = None
    is_default_role = upstream_role_json['name'] in UserRolePresets.INITIAL_ROLES.keys()

    sync_match = None
    name_match = None

    for downstream_role in downstream_roles:
        if upstream_role_json['_id'] == downstream_role.upstream_id:
            sync_match = downstream_role
        elif upstream_role_json['name'] == downstream_role.name:
            name_match = downstream_role

    if sync_match:
        matching_role, conflicting_role = sync_match, name_match
    elif name_match:
        if (is_default_role and _has_matching_permissions(upstream_role_json, name_match)) or ignore_conflicts:
            matching_role, conflicting_role = name_match, None
        else:
            matching_role, conflicting_role = None, name_match

    return (matching_role, conflicting_role, is_default_role)


def _has_matching_permissions(upstream_role_json, downstream_role):
    upstream_permissions = HqPermissions.wrap(upstream_role_json['permissions'])

    return upstream_permissions == downstream_role.permissions


def _copy_role_attributes(source_role_json, dest_role):
    dest_role.name = source_role_json['name']
    dest_role.default_landing_page = source_role_json['default_landing_page']
    dest_role.is_non_admin_editable = source_role_json['is_non_admin_editable']
    dest_role.upstream_id = source_role_json['_id']


def update_case_search_config(domain_link, is_pull=False, overwrite=False):
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


def update_data_dictionary(domain_link, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        master_results = remote_get_data_dictionary(domain_link)
    else:
        master_results = local_get_data_dictionary(domain_link.master_domain)

    # Start from an empty set of CaseTypes, CasePropertyGroups and CaseProperties in the linked domain.
    CaseType.objects.filter(domain=domain_link.linked_domain).delete()

    # Create CaseType and CaseProperty as necessary
    for case_type_name, case_type_desc in master_results.items():
        case_type_obj = CaseType.get_or_create(domain_link.linked_domain, case_type_name)
        case_type_obj.description = case_type_desc['description']
        case_type_obj.fully_generated = case_type_desc['fully_generated']
        case_type_obj.is_deprecated = case_type_desc['is_deprecated']
        case_type_obj.save()

        for group_name, group_desc in case_type_desc['groups'].items():
            if group_name:
                group_obj, created = CasePropertyGroup.objects.get_or_create(
                    name=group_name,
                    case_type=case_type_obj,
                    description=group_desc['description'],
                    index=group_desc['index']
                )

            for case_property_name, case_property_desc in group_desc['properties'].items():
                case_property_obj = CaseProperty.get_or_create(case_property_name,
                                                            case_type_obj.name,
                                                            domain_link.linked_domain)
                case_property_obj.description = case_property_desc['description']
                case_property_obj.deprecated = case_property_desc['deprecated']
                case_property_obj.data_type = case_property_desc['data_type']
                if group_name:
                    case_property_obj.group = group_obj
                case_property_obj.save()


def update_tableau_server_and_visualizations(domain_link, is_pull=False, overwrite=False):
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
    server_model.save()

    master_results_visualizations = master_results['visualizations']
    local_visualizations = TableauVisualization.objects.all().filter(
        domain=domain_link.linked_domain)
    vis_by_view_url = {}
    vis_by_upstream_id = {}
    for vis in local_visualizations:
        vis_by_view_url[vis.view_url] = vis
        if vis.upstream_id:
            vis_by_upstream_id[vis.upstream_id] = vis

    for master_vis in master_results_visualizations:
        vis = vis_by_upstream_id.get(master_vis['id']) or vis_by_view_url.get(master_vis['view_url'])
        if not vis:
            vis = TableauVisualization(domain=domain_link.linked_domain, server=server_model)
        vis_by_upstream_id[master_vis['id']] = vis
        vis.upstream_id = master_vis['id']
        vis.domain = domain_link.linked_domain
        vis.server = server_model
        vis.view_url = master_vis['view_url']
        vis.title = master_vis['title']
        vis.save()


def update_dialer_settings(domain_link, is_pull=False, overwrite=False):
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


def update_otp_settings(domain_link, is_pull=False, overwrite=False):
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


def update_hmac_callout_settings(domain_link, is_pull=False, overwrite=False):
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


def update_auto_update_rule(domain_link, id, is_pull=False, overwrite=False):
    upstream_rule_definition = local_get_auto_update_rule(domain_link.master_domain, id)
    downstream_rule = get_or_create_downstream_rule(domain_link.linked_domain, upstream_rule_definition)
    _update_rule(downstream_rule, upstream_rule_definition)


def get_or_create_downstream_rule(domain, upstream_definition):
    try:
        downstream_rule = AutomaticUpdateRule.objects.get(
            upstream_id=upstream_definition['rule']['id'],
            domain=domain,
            deleted=False
        )
    except AutomaticUpdateRule.DoesNotExist:
        downstream_rule = AutomaticUpdateRule(
            domain=domain,
            active=upstream_definition['rule']['active'],
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
            upstream_id=upstream_definition['rule']['id']
        )

    return downstream_rule


def _update_rule(rule, definition):
    with transaction.atomic():
        _update_rule_properties(rule, definition['rule'])

        rule.delete_criteria()
        rule.delete_actions()

        _create_rule_criteria(rule, definition['criteria'])
        _create_rule_actions(rule, definition['actions'])


def _update_rule_properties(rule, definition):
    rule.name = definition['name']
    rule.case_type = definition['case_type']
    rule.filter_on_server_modified = definition['filter_on_server_modified']
    rule.server_modified_boundary = definition['server_modified_boundary']
    rule.active = definition['active']
    rule.save()


def _create_rule_criteria(rule, criteria_definition):
    # Largely from data_interfaces/forms.py - save_criteria()
    for criteria in criteria_definition:
        definition = None

        if criteria['match_property_definition']:
            definition = MatchPropertyDefinition.objects.create(
                property_name=criteria['match_property_definition']['property_name'],
                property_value=criteria['match_property_definition']['property_value'],
                match_type=criteria['match_property_definition']['match_type'],
            )
        elif criteria['custom_match_definition']:
            definition = CustomMatchDefinition.objects.create(
                name=criteria['custom_match_definition']['name'],
            )
        elif criteria['closed_parent_definition']:
            definition = ClosedParentDefinition.objects.create()
        elif criteria['location_filter_definition']:
            definition = LocationFilterDefinition.objects.create(
                location_id=criteria['location_filter_definition']['location_id'],
                include_child_locations=criteria['location_filter_definition']['include_child_locations'],
            )

        new_criteria = CaseRuleCriteria(rule=rule)
        new_criteria.definition = definition
        new_criteria.save()


def _create_rule_actions(rule, action_definition):
    # Largely from data_interfacees/forms.py - save_actions()
    for action in action_definition:
        definition = None

        if action['update_case_definition']:
            definition = UpdateCaseDefinition(close_case=action['update_case_definition']['close_case'])
            properties = []
            for propertyItem in action['update_case_definition']['properties_to_update']:
                properties.append(
                    UpdateCaseDefinition.PropertyDefinition(
                        name=propertyItem['name'],
                        value_type=propertyItem['value_type'],
                        value=propertyItem['value'],
                    )
                )
            definition.set_properties_to_update(properties)
            definition.save()
        elif action['custom_action_definition']:
            definition = CustomActionDefinition.objects.create(
                name=action['custom_action_definition']['name'],
            )

        action = CaseRuleAction(rule=rule)
        action.definition = definition
        action.save()


def update_auto_update_rules(domain_link, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        upstream_rules = remote_get_auto_update_rules(domain_link)
    else:
        upstream_rules = local_get_auto_update_rules(domain_link.master_domain)

    downstream_rules = AutomaticUpdateRule.by_domain(
        domain_link.linked_domain,
        AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        active_only=False
    )

    for upstream_rule_def in upstream_rules:
        # Grab local rule by upstream ID
        try:
            downstream_rule = downstream_rules.get(upstream_id=upstream_rule_def['rule']['id'])
        except AutomaticUpdateRule.DoesNotExist:
            downstream_rule = None

        # If no corresponding local rule, make a new rule
        if not downstream_rule:
            downstream_rule = AutomaticUpdateRule(
                domain=domain_link.linked_domain,
                active=upstream_rule_def['rule']['active'],
                workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
                upstream_id=upstream_rule_def['rule']['id']
            )

        _update_rule(downstream_rule, upstream_rule_def)


def _convert_reports_permissions(domain_link, master_results):
    """Mutates the master result docs to convert dynamic report permissions.
    """
    report_map = get_static_report_mapping(domain_link.master_domain, domain_link.linked_domain)
    report_configs = get_report_and_registry_report_configs_for_domain(domain_link.linked_domain)
    report_map.update({
        c.report_meta.master_id: c._id
        for c in report_configs
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


def _get_new_tableau_report_permissions(downstream_domain_visualizations, upstream_permissions,
                                        original_downstream_permissions):
    new_downstream_view_tableau_list = []
    for viz in downstream_domain_visualizations:
        upstream_viz_enabled = viz.upstream_id and viz.upstream_id in upstream_permissions.view_tableau_list
        no_upstream_viz_and_viz_enabled_downstream = (not viz.upstream_id
            and str(viz.id) in original_downstream_permissions.view_tableau_list)
        if upstream_viz_enabled or no_upstream_viz_and_viz_enabled_downstream:
            new_downstream_view_tableau_list.append(str(viz.id))
    return new_downstream_view_tableau_list
