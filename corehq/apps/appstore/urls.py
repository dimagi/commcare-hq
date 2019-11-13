from django.conf.urls import url

from corehq.apps.appstore.views import (
    CommCareExchangeHomeView,
    ProjectInformationView,
    approve_app,
    copy_snapshot,
    project_documentation_file,
    project_image,
)

urlpatterns = [
    url(r'^$', CommCareExchangeHomeView.as_view(), name=CommCareExchangeHomeView.urlname),

    url(r'^(?P<snapshot>[\w\.-]+)/info/$', ProjectInformationView.as_view(),
        name=ProjectInformationView.urlname),

    url(r'^(?P<snapshot>[\w\.-]+)/approve/$', approve_app, name='approve_appstore_app'),
    url(r'^(?P<snapshot>[\w\.-]+)/copy/$', copy_snapshot, name='domain_copy_snapshot'),
    url(r'^(?P<snapshot>[\w\.-]+)/image/$', project_image, name='appstore_project_image'),
    url(r'^(?P<snapshot>[\w\.-]+)/documentation_file/$', project_documentation_file,
        name='appstore_project_documentation_file'),
]
