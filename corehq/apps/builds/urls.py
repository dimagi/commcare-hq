from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from .views import EditMenuView, import_build, post, get, get_all

urlpatterns = [
    url(r'^edit_menu/$', EditMenuView.as_view(), name=EditMenuView.urlname),
    url(r'^import/$', import_build, name='import_build'),
    url(r'^post/$', post),
    url(r'^(?P<version>.+)/(?P<build_number>\d+)/(?P<path>.+)$', get),
    url(r'^$', get_all),
]
