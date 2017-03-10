from corehq.toggles import PREVIEW_APP
from corehq.apps.analytics import ab_tests


def should_show_preview_app(request, app, username):
    return (PREVIEW_APP.enabled(app.domain) or PREVIEW_APP.enabled(username)) and not app.is_remote_app()
