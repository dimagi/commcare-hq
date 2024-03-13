from collections import defaultdict

from corehq import feature_previews, toggles
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.fixtures.models import LookupTable, LookupTableRow
from corehq.apps.linked_domain.util import _clean_json
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.products.views import ProductFieldsView
from corehq.apps.users.models import UserRole
from corehq.apps.users.views.mobile import UserFieldsView
from corehq.apps.integration.models import DialerSettings, GaenOtpServerSettings, HmacCalloutSettings
from corehq.apps.reports.models import TableauServer, TableauVisualization
from corehq.apps.data_interfaces.models import AutomaticUpdateRule


def get_tableau_server_and_visualizations(domain):
    server, created = TableauServer.objects.get_or_create(domain=domain)
    visualizations = TableauVisualization.objects.all().filter(domain=domain)
    vis_list = []
    for vis in visualizations:
        vis_list.append({
            'domain': domain,
            'title': vis.title,
            'server': server,
            'view_url': vis.view_url,
            'id': vis.id,
        })
    return {
        'server': {
            'domain': domain,
            'server_type': server.server_type,
            'server_name': server.server_name,
            'validate_hostname': server.validate_hostname,
            'target_site': server.target_site,
        },
        'visualizations': vis_list,
    }


def get_enabled_toggles_and_previews(domain):
    return {
        'toggles': get_enabled_toggles(domain),
        'previews': get_enabled_previews(domain)
    }


def get_enabled_toggles(domain):
    return list(toggles.toggles_dict(domain=domain))


def get_enabled_previews(domain):
    return list(feature_previews.previews_dict(domain=domain))


def get_custom_data_models(domain, limit_types=None):
    fields = defaultdict(dict)
    for field_view in [LocationFieldsView, ProductFieldsView, UserFieldsView]:
        if limit_types and field_view.field_type not in limit_types:
            continue
        model = CustomDataFieldsDefinition.get(domain, field_view.field_type)
        if model:
            fields[field_view.field_type]['fields'] = [
                {
                    'id': field.id,
                    'slug': field.slug,
                    'is_required': field.is_required,
                    'label': field.label,
                    'choices': field.choices,
                    'regex': field.regex,
                    'regex_msg': field.regex_msg,
                } for field in model.get_fields()
            ]
            if field_view.show_profiles:
                fields[field_view.field_type]['profiles'] = [
                    profile.to_json()
                    for profile in model.get_profiles()
                ]
    return fields


def get_fixture(domain, tag):
    data_type = LookupTable.objects.by_domain_tag(domain, tag)
    return {
        "data_type": data_type,
        "data_items": list(LookupTableRow.objects.filter(
            domain=domain,
            table_id=data_type.id,
        )),
    }


def get_user_roles(domain):
    def _to_json(role):
        return _clean_json(role.to_json())

    return [_to_json(role) for role in UserRole.objects.get_by_domain(domain)]


def get_data_dictionary(domain):
    data_dictionary = {}
    for case_type_obj in CaseType.objects.filter(domain=domain):
        case_type = {
            'domain': domain,
            'description': case_type_obj.description,
            'fully_generated': case_type_obj.fully_generated,
            'is_deprecated': case_type_obj.is_deprecated,
            'groups': {},
        }
        case_properties = (CaseProperty.objects
                        .filter(case_type=case_type_obj)
                        .prefetch_related("group")
                        .order_by("group__name"))
        for property in case_properties:
            group = case_type["groups"].get(property.group_name)

            if not group:
                group = {"properties": {}}
                if property.group:
                    group["description"] = property.group.description
                    group["index"] = property.group.index
                case_type["groups"][property.group_name] = group

            group["properties"][property.name] = {
                'description': property.description,
                'deprecated': property.deprecated,
                'data_type': property.data_type,
            }

        data_dictionary[case_type_obj.name] = case_type
    return data_dictionary


def get_dialer_settings(domain):
    settings, created = DialerSettings.objects.get_or_create(domain=domain)
    return {
        'domain': domain,
        'aws_instance_id': settings.aws_instance_id,
        'is_enabled': settings.is_enabled,
        'dialer_page_header': settings.dialer_page_header,
        'dialer_page_subheader': settings.dialer_page_subheader,
    }


def get_otp_settings(domain):
    settings, created = GaenOtpServerSettings.objects.get_or_create(domain=domain)
    return {
        'domain': domain,
        'is_enabled': settings.is_enabled,
        'server_url': settings.server_url,
        'auth_token': settings.auth_token,
    }


def get_hmac_callout_settings(domain):
    settings, created = HmacCalloutSettings.objects.get_or_create(domain=domain)
    return {
        'domain': domain,
        'destination_url': settings.destination_url,
        'is_enabled': settings.is_enabled,
        'api_key': settings.api_key,
        'api_secret': settings.api_secret,
    }


def rule_to_dict(rule):
    rule_data = rule.to_dict()
    del rule_data['rule']['last_run']
    del rule_data['rule']['locked_for_editing']

    return rule_data


def get_auto_update_rule(domain, id):
    rule = AutomaticUpdateRule.objects.get(id=id)
    return rule_to_dict(rule)


def get_auto_update_rules(domain):
    rules = AutomaticUpdateRule.by_domain(
        domain,
        # For now only grab those rules that update cases, not conditional alerts for messaging
        AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        active_only=False
    )

    return [rule_to_dict(rule) for rule in rules]
