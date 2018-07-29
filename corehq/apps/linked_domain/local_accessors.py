from __future__ import absolute_import

from __future__ import unicode_literals
from corehq import toggles, feature_previews
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
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
        model = get_by_domain_and_type(domain, field_view.field_type)
        if model:
            fields[field_view.field_type] = model.to_json()['fields']
    return fields


def get_user_roles(domain):
    def _to_json(role):
        return _clean_json(role.to_json())

    return [_to_json(role) for role in UserRole.by_domain(domain)]
