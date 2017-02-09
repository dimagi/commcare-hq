from corehq.toggles import PREVIEW_APP
from corehq.apps.analytics import ab_tests


def should_show_preview_app(request, domain_obj, username):
    return PREVIEW_APP.enabled(domain_obj.name) or PREVIEW_APP.enabled(username)
