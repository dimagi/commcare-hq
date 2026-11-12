from django.urls import reverse

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import (
    get_app_ids_in_domain,
    get_latest_released_app,
)
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.domain.utils import is_domain_active
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import HqPermissions


def public_webforms_enabled(domain):
    return (
        is_domain_active(domain)
        and domain_has_privilege(domain, privileges.PUBLIC_WEBFORMS)
        and toggles.PUBLIC_WEBFORMS.enabled(domain, namespace=toggles.NAMESPACE_DOMAIN)
    )


def can_access_public_webforms(request, domain):
    return (
        domain_has_privilege(domain, privileges.PUBLIC_WEBFORMS)
        and request.couch_user.has_permission(
            domain, get_permission_name(HqPermissions.edit_public_webforms)
        )
        and toggles.PUBLIC_WEBFORMS.enabled_for_request(request)
    )


def get_create_public_webform_url(request, form):
    app = form.get_app()
    if not (
        can_access_public_webforms(request, app.domain)
        and get_latest_released_eligible_form(app.domain, app.id, form.unique_id)
    ):
        return None

    return reverse(
        'create_public_webform',
        args=[app.domain],
        query={'app_id': app.id, 'form_unique_id': form.unique_id},
    )


def is_app_live(domain, app_id):
    return app_id in get_live_app_ids(domain)


def get_live_app_ids(domain):
    return set(get_app_ids_in_domain(domain))


def get_public_webform_eligible_form(domain, app_id, form_unique_id):
    if not is_app_live(domain, app_id):
        return None
    return get_latest_released_eligible_form(domain, app_id, form_unique_id)


def get_latest_released_eligible_form(domain, app_id, form_unique_id):
    app = get_latest_released_app(domain, app_id)
    if app is None or not app.can_generate_session_endpoints:
        return None
    try:
        form = app.get_form(form_unique_id)
    except FormNotFoundException:
        return None
    if form.get_module().module_type != 'basic' or form.requires_case():
        return None
    return form
