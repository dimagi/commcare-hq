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
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
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
from corehq.toggles.shortcuts import set_toggle


def update_model_type(domain_link, model_type, model_detail=None):
    update_fn = {
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

    kwargs = model_detail or {}
    update_fn(domain_link, **kwargs)


def update_toggles(domain_link):
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


def update_previews(domain_link):
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
        # FIXME Gets a requests.request(...) response object, which does
        # not support the operations below. It has never worked.
        master_results = remote_fixture(domain_link, tag)
    else:
        master_results = local_fixture(domain_link.master_domain, tag)

    master_data_type = master_results["data_type"]
    if not master_data_type.is_global:
        raise UnsupportedActionError(_("Found non-global lookup table '{}'.").format(master_data_type.tag))

    # Update data type
    try:
        linked_data_type = LookupTable.objects.by_domain_tag(
            domain_link.linked_domain, master_data_type.tag)
        is_existing_table = True
    except LookupTable.DoesNotExist:
        linked_data_type = LookupTable(domain=domain_link.linked_domain)
        is_existing_table = False
    for field in LookupTable._meta.fields:
        if field.attname not in ["id", "domain"]:
            value = getattr(master_data_type, field.attname)
            setattr(linked_data_type, field.attname, value)
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


def update_user_roles(domain_link):
    if domain_link.is_remote:
        master_results = remote_get_user_roles(domain_link)
    else:
        master_results = local_get_user_roles(domain_link.master_domain)

    _convert_reports_permissions(domain_link, master_results)

    local_roles = UserRole.objects.get_by_domain(domain_link.linked_domain, include_archived=True)
    local_roles_by_name = {}
    local_roles_by_upstream_id = {}
    for role in local_roles:
        local_roles_by_name[role.name] = role
        if role.upstream_id:
            local_roles_by_upstream_id[role.upstream_id] = role

    is_embedded_tableau_enabled = EMBEDDED_TABLEAU.enabled(domain_link.linked_domain)
    if is_embedded_tableau_enabled:
        visualizations_for_linked_domain = TableauVisualization.objects.filter(
            domain=domain_link.linked_domain)

    # Update downstream roles based on upstream roles
    for role_def in master_results:
        role = local_roles_by_upstream_id.get(role_def['_id']) or local_roles_by_name.get(role_def['name'])
        if not role:
            role = UserRole(domain=domain_link.linked_domain)
        local_roles_by_upstream_id[role_def['_id']] = role
        role.upstream_id = role_def['_id']

        role.name = role_def["name"]
        role.default_landing_page = role_def["default_landing_page"]
        role.is_non_admin_editable = role_def["is_non_admin_editable"]
        role.save()

        permissions = HqPermissions.wrap(role_def["permissions"])
        if is_embedded_tableau_enabled:
            permissions.view_tableau_list = _get_new_tableau_report_permissions(
                visualizations_for_linked_domain, permissions, role.permissions)
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

    # Start from an empty set of CaseTypes, CasePropertyGroups and CaseProperties in the linked domain.
    CaseType.objects.filter(domain=domain_link.linked_domain).delete()

    # Create CaseType and CaseProperty as necessary
    for case_type_name, case_type_desc in master_results.items():
        case_type_obj = CaseType.get_or_create(domain_link.linked_domain, case_type_name)
        case_type_obj.description = case_type_desc['description']
        case_type_obj.fully_generated = case_type_desc['fully_generated']
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
                    case_property_obj.group = group_name
                    case_property_obj.group_obj = group_obj
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


def update_auto_update_rules(domain_link):
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
        # Grab local rule by upstream ID (preferred) or by name
        try:
            downstream_rule = downstream_rules.get(upstream_id=upstream_rule_def['rule']['id'])
        except AutomaticUpdateRule.DoesNotExist:
            try:
                downstream_rule = downstream_rules.get(name=upstream_rule_def['rule']['name'])
            except AutomaticUpdateRule.MultipleObjectsReturned:
                # If there are multiple rules with the same name, overwrite the first.
                downstream_rule = downstream_rules.filter(name=upstream_rule_def['rule']['name']).first()
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

        # Copy all the contents from old rule to new rule
        with transaction.atomic():

            downstream_rule.name = upstream_rule_def['rule']['name']
            downstream_rule.case_type = upstream_rule_def['rule']['case_type']
            downstream_rule.filter_on_server_modified = upstream_rule_def['rule']['filter_on_server_modified']
            downstream_rule.server_modified_boundary = upstream_rule_def['rule']['server_modified_boundary']
            downstream_rule.active = upstream_rule_def['rule']['active']
            downstream_rule.save()

            downstream_rule.delete_criteria()
            downstream_rule.delete_actions()

            # Largely from data_interfaces/forms.py - save_criteria()
            for criteria in upstream_rule_def['criteria']:
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

                new_criteria = CaseRuleCriteria(rule=downstream_rule)
                new_criteria.definition = definition
                new_criteria.save()

            # Largely from data_interfacees/forms.py - save_actions()
            for action in upstream_rule_def['actions']:
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

                action = CaseRuleAction(rule=downstream_rule)
                action.definition = definition
                action.save()


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
