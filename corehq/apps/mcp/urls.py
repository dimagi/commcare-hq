from django.urls import re_path as url

from corehq.apps.mcp.views import (
    mcp_endpoint,
    oauth_protected_resource_metadata,
)

urlpatterns = [
    url(r'^mcp$', mcp_endpoint, name='mcp'),
    url(r'^\.well-known/oauth-protected-resource/mcp$',
        oauth_protected_resource_metadata,
        name='oauth_protected_resource_metadata_mcp'),
]
