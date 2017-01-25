from corehq.toggles import PREVIEW_APP
from corehq.apps.analytics import ab_tests


def should_show_preview_app(request, domain_obj, username):
    live_preview_ab = ab_tests.ABTest(ab_tests.LIVE_PREVIEW, request)
    if domain_obj.is_onboarding_domain and live_preview_ab.version == ab_tests.LIVE_PREVIEW_ENABLED:
        return True
    elif domain_obj.is_onboarding_domain:
        return False

    return PREVIEW_APP.enabled(domain_obj.name) or PREVIEW_APP.enabled(username)
