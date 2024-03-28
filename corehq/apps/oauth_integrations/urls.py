from django.urls import re_path as url

from corehq.apps.oauth_integrations.views.google import (
    redirect_oauth_view,
    call_back_view
)

urlpatterns = [
    # OAuth redirect views
    url(r"^google_sheets_oauth/redirect/$",
        redirect_oauth_view,
        name="google_sheet_oauth_redirect"),
    url(r"^google_sheets_oauth/callback/$",
        call_back_view,
        name="google_sheet_oauth_callback")
]
