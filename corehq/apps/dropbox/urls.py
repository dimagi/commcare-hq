from django.conf.urls import *

from .views import DropboxAuthCallback, DropboxAuthInitiate

urlpatterns = patterns('corehq.apps.dropbox.views',
    url(r'^initiate/$', DropboxAuthInitiate.as_view(), name=DropboxAuthInitiate.slug),
    url(r'^finalize/$', DropboxAuthCallback.as_view(), name=DropboxAuthCallback.slug),
)
