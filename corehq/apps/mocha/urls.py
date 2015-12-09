from django.conf.urls import patterns, url

from .views import MochaView

urlpatterns = patterns('corehq.apps.mocha.views',
    url(r'^(?P<app>[\w\-_]+)/$', MochaView.as_view(), name=MochaView.urlname),
    url(r'^(?P<app>[\w\-_]+)/(?P<config>[\w\-_]+)$', MochaView.as_view(), name=MochaView.urlname)
)
