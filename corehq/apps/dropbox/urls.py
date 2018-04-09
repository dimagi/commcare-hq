from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from .views import DropboxAuthCallback, DropboxAuthInitiate

urlpatterns = [
    url(r'^initiate/$', DropboxAuthInitiate.as_view(), name=DropboxAuthInitiate.slug),
    url(r'^finalize/$', DropboxAuthCallback.as_view(), name=DropboxAuthCallback.slug),
]
