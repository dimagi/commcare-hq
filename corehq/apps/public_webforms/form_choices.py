from corehq.apps.app_manager.dbaccessors import (
    get_latest_released_app,
    get_latest_released_app_versions_by_app_id,
)
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.public_webforms.models import PublicWebformType


def get_public_webform_choices(domain):
    """Return the drilldown tree of applications, menus, and eligible forms
    from latest released app builds.

    The structure is ``[{'id', 'name', 'version', 'menus': [{'id', 'name',
    'forms': [{'id', 'name', 'session_type'}]}]}]``. Menus and applications
    with no eligible forms are omitted.
    """
    options = []
    for app_id in get_latest_released_app_versions_by_app_id(domain):
        app = get_latest_released_app(domain, app_id)
        if app is None:
            continue
        menus = []
        for module in app.get_modules():
            if module.module_type != 'basic':
                continue
            forms = [
                {
                    'id': form.unique_id,
                    'name': form.default_name(),
                    'session_type': get_public_webform_type(form).value,
                }
                for form in module.get_forms()
                if not form.requires_case()
            ]
            if forms:
                menus.append({
                    'id': module.unique_id,
                    'name': module.default_name(app),
                    'forms': forms,
                })
        if menus:
            options.append({
                'id': app_id,
                'name': app.name,
                'version': app.version,
                'menus': menus,
            })
    return options


def get_public_webform_eligible_form(domain, app_id, form_unique_id):
    app = get_latest_released_app(domain, app_id)
    if app is None:
        return None
    try:
        form = app.get_form(form_unique_id)
    except FormNotFoundException:
        return None
    if form.get_module().module_type != 'basic' or form.requires_case():
        return None
    return form


def get_public_webform_type(form):
    return (
        PublicWebformType.REGISTRATION
        if form.is_registration_form()
        else PublicWebformType.SURVEY
    )
