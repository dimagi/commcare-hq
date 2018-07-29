from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.appstore.views import (
    CommCareExchangeHomeView,
    ProjectInformationView,
    DeploymentsView,
    DeploymentInfoView,
    MediaFilesView,
    deployments_api,
    approve_app,
    copy_snapshot,
    import_app,
    project_image,
    project_documentation_file,
)

urlpatterns = [
    url(r'^$', CommCareExchangeHomeView.as_view(), name=CommCareExchangeHomeView.urlname),

    url(r'^(?P<snapshot>[\w\.-]+)/info/$', ProjectInformationView.as_view(),
        name=ProjectInformationView.urlname),

    url(r'^deployments/$', DeploymentsView.as_view(), name=DeploymentsView.urlname),
    url(r'^deployments/api/$', deployments_api, name='deployments_api'),
    url(r'^deployments/(?P<snapshot>[\w\.-]+)/info/$',
        DeploymentInfoView.as_view(), name=DeploymentInfoView.urlname),

    url(r'^(?P<snapshot>[\w\.-]+)/approve/$', approve_app, name='approve_appstore_app'),
    url(r'^(?P<snapshot>[\w\.-]+)/copy/$', copy_snapshot, name='domain_copy_snapshot'),
    url(r'^(?P<snapshot>[\w\.-]+)/importapp/$', import_app, name='import_app_from_snapshot'),
    url(r'^(?P<snapshot>[\w\.-]+)/image/$', project_image, name='appstore_project_image'),
    url(r'^(?P<snapshot>[\w\.-]+)/documentation_file/$', project_documentation_file,
        name='appstore_project_documentation_file'),
    url(r'^(?P<snapshot>[\w\.-]+)/multimedia/$',
        MediaFilesView.as_view(), name=MediaFilesView.urlname),
]

