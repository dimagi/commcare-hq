from collections import defaultdict

from corehq import feature_previews, toggles
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.fixtures.dbaccessors import get_fixture_data_type_by_tag, get_fixture_items_for_data_type
from corehq.apps.linked_domain.util import _clean_json
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.products.views import ProductFieldsView
from corehq.apps.users.models import UserRole
from corehq.apps.users.views.mobile import UserFieldsView


def get_toggles_previews(domain):
    return {
        'toggles': list(toggles.toggles_dict(domain=domain)),
        'previews': list(feature_previews.previews_dict(domain=domain))
    }


def get_custom_data_models(domain, limit_types=None):
    fields = defaultdict(dict)
    for field_view in [LocationFieldsView, ProductFieldsView, UserFieldsView]:
        if limit_types and field_view.field_type not in limit_types:
            continue
        model = CustomDataFieldsDefinition.get(domain, field_view.field_type)
        if model:
            fields[field_view.field_type]['fields'] = [
                {
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
    data_type = get_fixture_data_type_by_tag(domain, tag)
    return {
        "data_type": data_type,
        "data_items": get_fixture_items_for_data_type(domain, data_type._id),
    }


def get_user_roles(domain):
    def _to_json(role):
        return _clean_json(role.to_json())

    return [_to_json(role) for role in UserRole.by_domain(domain)]


def get_data_dictionary(domain):
    data_dictionary = {}
    for case_type in CaseType.objects.filter(domain=domain):
        entry = {
            'domain': domain,
            'description': case_type.description,
            'fully_generated': case_type.fully_generated
        }

        entry['properties'] = {
            property.name: {
                'description': property.description,
                'deprecated': property.deprecated,
                'data_type': property.data_type,
                'group': property.group
            }
            for property in CaseProperty.objects.filter(case_type=case_type)}

        data_dictionary[case_type.name] = entry
    return data_dictionary
