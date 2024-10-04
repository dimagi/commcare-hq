from django.urls import re_path as url

from .views import MochaView

urlpatterns = [
    url(r'^(?P<app>[\w\-_]+)/$', MochaView.as_view(), name=MochaView.urlname),
    url(r'^(?P<app>[\w\-_]+)/(?P<bootstrap_version>bootstrap[35])/?$',
        MochaView.as_view(), name=MochaView.urlname),
    url(r'^(?P<app>[\w\-_]+)/(?P<config>[\w\-_]+)$', MochaView.as_view(), name=MochaView.urlname),
    url(r'^(?P<app>[\w\-_]+)/(?P<config>[\w\-_]+)/(?P<bootstrap_version>bootstrap[35])/?$',
        MochaView.as_view(), name=MochaView.urlname),
]
