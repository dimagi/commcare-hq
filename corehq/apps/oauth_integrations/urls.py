from django.conf.urls import url

from corehq.apps.oauth_integrations.views.google import (
    google_sheet_oauth_redirect,
    google_sheet_oauth_callback
)

urlpatterns = [
    # OAuth redirect views
    url(r"^google_sheets_oauth/callback/$",
        google_sheet_oauth_callback,
        name="google_sheet_oauth_callback")
]
