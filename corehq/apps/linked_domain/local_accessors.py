from corehq import feature_previews, toggles
from corehq.apps.custom_data_fields.models import SQLCustomDataFieldsDefinition
from corehq.apps.fixtures.dbaccessors import get_fixture_data_types, get_fixture_items_for_data_type
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
    fields = {}
    for field_view in [LocationFieldsView, ProductFieldsView, UserFieldsView]:
        if limit_types and field_view.field_type not in limit_types:
            continue
        model = SQLCustomDataFieldsDefinition.get(domain, field_view.field_type)
        if model:
            fields[field_view.field_type] = [
                {
                    'slug': field.slug,
                    'is_required': field.is_required,
                    'label': field.label,
                    'choices': field.choices,
                    'regex': field.regex,
                    'regex_msg': field.regex_msg,
                } for field in model.get_fields()
            ]
    return fields


def get_fixtures(domain):
    types = get_fixture_data_types(domain)
    return {
        "data_types": types,
        "data_items": {
            t._id: get_fixture_items_for_data_type(domain, t._id)
            for t in types
        },
    }


def get_user_roles(domain):
    def _to_json(role):
        return _clean_json(role.to_json())

    return [_to_json(role) for role in UserRole.by_domain(domain)]
