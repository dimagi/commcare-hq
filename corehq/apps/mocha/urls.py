from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from .views import MochaView

urlpatterns = [
    url(r'^(?P<app>[\w\-_]+)/$', MochaView.as_view(), name=MochaView.urlname),
    url(r'^(?P<app>[\w\-_]+)/(?P<config>[\w\-_]+)$', MochaView.as_view(), name=MochaView.urlname)
]
