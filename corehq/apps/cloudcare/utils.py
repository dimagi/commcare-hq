from corehq.toggles import PREVIEW_APP
from corehq.apps.analytics import ab_tests


def should_show_preview_app(request, domain_obj, username):
    if domain_obj.is_onboarding_domain:
        return True
    elif domain_obj.is_onboarding_domain and not request.couch_user.is_dimagi:
        return False

    return PREVIEW_APP.enabled(domain_obj.name) or PREVIEW_APP.enabled(username)
