from django.urls import re_path as url

from .views import DropboxAuthCallback, DropboxAuthInitiate

urlpatterns = [
    url(r'^initiate/$', DropboxAuthInitiate.as_view(), name=DropboxAuthInitiate.slug),
    url(r'^finalize/$', DropboxAuthCallback.as_view(), name=DropboxAuthCallback.slug),
]
