from dropbox.client import DropboxOAuth2Flow

from django.conf import settings
from django.core.urlresolvers import reverse

from dimagi.utils.web import get_url_base


def get_dropbox_auth_flow(session):
    from .views import DropboxAuthCallback

    redirect_uri = '{}{}'.format(
        get_url_base(),
        reverse(DropboxAuthCallback.slug),
    )
    return DropboxOAuth2Flow(settings.DROPBOX_KEY, settings.DROPBOX_SECRET, redirect_uri,
         session, "dropbox-auth-csrf-token")
