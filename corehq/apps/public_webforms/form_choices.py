from dimagi.utils.couch.database import iter_docs

from corehq.apps.app_manager.dbaccessors import (
    get_latest_released_build_ids_by_app_id,
    wrap_app,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.public_webforms.models import PublicWebformType
from corehq.apps.public_webforms.utils import get_live_app_ids
from corehq.util.quickcache import quickcache


def get_public_webform_choices(domain):
    """Return the drilldown tree of applications, menus, and eligible forms
    from latest released app builds. Deleted applications, and menus and
    applications with no eligible forms, are omitted.
    """
    live_app_ids = get_live_app_ids(domain)
    build_ids = {
        build_id
        for app_id, build_id in get_latest_released_build_ids_by_app_id(domain).items()
        if app_id in live_app_ids
    }
    return _get_choices_for_builds(build_ids)


# builds are immutable, so the choices for a set of build ids never go stale
@quickcache(['build_ids'], timeout=24 * 60 * 60)
def _get_choices_for_builds(build_ids):
    choices = (
        _get_build_choice(wrap_app(doc))
        for doc in iter_docs(Application.get_db(), build_ids)
    )
    return sorted(
        (choice for choice in choices if choice),
        key=lambda x: x['name'].casefold(),
    )


def _get_build_choice(app):
    if not app.can_generate_session_endpoints:
        return None
    menus = []
    for module in app.get_modules():
        if module.module_type != 'basic':
            continue
        forms = [
            {
                'id': form.unique_id,
                'name': form.default_name(),
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
    if not menus:
        return None
    return {
        'id': app.copy_of,
        'name': app.name,
        'version': app.version,
        'menus': menus,
    }


def get_public_webform_type(form):
    return (
        PublicWebformType.REGISTRATION
        if form.is_registration_form()
        else PublicWebformType.SURVEY
    ).value
