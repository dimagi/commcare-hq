from django.http import JsonResponse

from corehq import toggles, feature_previews
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
from corehq.apps.domain.decorators import api_key_auth
from corehq.apps.linked_domain.decorators import require_linked_domain
from corehq.apps.linked_domain.util import _clean_json
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.products.views import ProductFieldsView
from corehq.apps.users.models import UserRole


@api_key_auth
@require_linked_domain
def toggles_and_previews(request, domain):
    return JsonResponse({
        'toggles': list(toggles.toggles_dict(domain=domain)),
        'previews': list(feature_previews.previews_dict(domain=domain))
    })


@api_key_auth
@require_linked_domain
def custom_data_models(request, domain):
    fields = {}
    for field_view in (LocationFieldsView, ProductFieldsView, LocationFieldsView):
        model = get_by_domain_and_type(domain, field_view.field_type)
        if model:
            fields[field_view.field_type] = model.to_json()['fields']

    return JsonResponse(fields)


@api_key_auth
@require_linked_domain
def user_roles(request, domain):
    def _to_json(role):
        return _clean_json(role.to_json())

    roles = map(_to_json, UserRole.by_domain(domain))
    return JsonResponse({'user_roles': roles})
