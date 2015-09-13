from django.conf.urls import patterns, url

from .views import ChiefStatusPage, ChiefSubmodules, ChiefPrepare, ChiefDeploy, ChiefReleases


urlpatterns = patterns('corehq.apps.chief.views',
    url(r'^$', ChiefStatusPage.as_view(), name=ChiefStatusPage.urlname),
    url(r'^submodules/$', ChiefSubmodules.as_view(), name=ChiefSubmodules.urlname),
    url(r'^prepare/$', ChiefPrepare.as_view(), name=ChiefPrepare.urlname),
    url(r'^deploy/$', ChiefDeploy.as_view(), name=ChiefDeploy.urlname),
    url(r'^releases/$', ChiefReleases.as_view(), name=ChiefReleases.urlname),
)
