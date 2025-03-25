from django.conf import settings

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import (
    get_app_ids_in_domain,
    get_apps_in_domain,
    get_latest_build_doc,
    get_latest_build_id,
    get_latest_released_app_doc,
    get_latest_released_build_id,
)
from corehq.util.quickcache import quickcache


def can_user_access_web_app(user, app):
    """
    :param user: either a WebUser or CommCareUser
    :param app: app doc (not wrapped Application)
    """
    domain = app["domain"]
    # Backwards-compatibility - mobile users haven't historically required this permission
    has_access_via_permission = user.is_commcare_user()
    if user.is_web_user() or user.can_access_any_web_apps(domain):
        app_id = app.get("copy_of") or app.get("_id")
        has_access_via_permission = user.can_access_web_app(domain, app_id)

    has_access_via_group = True  # permission takes precedence over groups, so default to True
    if toggles.WEB_APPS_PERMISSIONS_VIA_GROUPS.enabled(domain):
        from corehq.apps.cloudcare.dbaccessors import (
            get_application_access_for_domain,
        )
        app_access = get_application_access_for_domain(domain)
        has_access_via_group = app_access.user_can_access_app(user, app)

    return has_access_via_permission and has_access_via_group


def get_latest_build_for_web_apps(domain, username, app_id):
    if (toggles.CLOUDCARE_LATEST_BUILD.enabled(domain) or toggles.CLOUDCARE_LATEST_BUILD.enabled(username)):
        return get_latest_build_doc(domain, app_id)
    else:
        return get_latest_released_app_doc(domain, app_id)


def get_latest_build_id_for_web_apps(domain, username, app_id):
    if (toggles.CLOUDCARE_LATEST_BUILD.enabled(domain) or toggles.CLOUDCARE_LATEST_BUILD.enabled(username)):
        return get_latest_build_id(domain, app_id)
    else:
        return get_latest_released_build_id(domain, app_id)


def get_web_apps_available_to_user(domain, user, is_preview=False, fetch_app_fn=get_latest_build_for_web_apps):
    """
    The fetch_app_fn is a function to fetch app docs, and should accept a domain, username and app_id if overridden
    """
    def is_web_app(app):
        return app.get('cloudcare_enabled') or is_preview

    apps = []
    app_ids = get_app_ids_in_domain(domain)
    for app_id in app_ids:
        app = fetch_app_fn(domain, user.username, app_id)
        if app and is_web_app(app) and can_user_access_web_app(user, app):
            apps.append(app)

    return apps


def should_show_preview_app(request, app, username):
    return not app.is_remote_app()


@quickcache(['domain'], timeout=24 * 60 * 60)
def get_mobile_ucr_count(domain):
    """
    Obtains the count of UCRs referenced across all applications in the specificed domain
    If the MOBILE_UCR feature flag is not enabled, returns zero
    If the ALLOW_WEB_APPS_RESTRICTION is not enabled, returns zero
    """
    if not toggles.MOBILE_UCR.enabled(domain):
        return 0

    if not toggles.ALLOW_WEB_APPS_RESTRICTION.enabled(domain):
        return 0

    apps = get_apps_in_domain(domain, include_remote=False)
    ucrs = [
        ucr
        for app in apps
        for module in app.get_report_modules()
        for ucr in module.report_configs
    ]
    return len(ucrs)


def should_restrict_web_apps_usage(domain, ucr_count):
    """
    This check is only applicable to domains that have both the MOBILE_UCR and ALLOW_WEB_APPS_RESTRICTION
    feature flags enabled.
    Given the number of UCRs referenced in applications across a domain, returns True if above
    the MAX_MOBILE_UCR_LIMIT or False otherwise.
    """
    if not toggles.MOBILE_UCR.enabled(domain):
        return False

    if not toggles.ALLOW_WEB_APPS_RESTRICTION.enabled(domain):
        return False

    return ucr_count > settings.MAX_MOBILE_UCR_LIMIT
