from django.conf.urls import url

from corehq.apps.appstore.views import (
    approve_app,
    project_documentation_file,
    project_image,
)

urlpatterns = [
    url(r'^(?P<snapshot>[\w\.-]+)/approve/$', approve_app, name='approve_appstore_app'),
    url(r'^(?P<snapshot>[\w\.-]+)/image/$', project_image, name='appstore_project_image'),
    url(r'^(?P<snapshot>[\w\.-]+)/documentation_file/$', project_documentation_file,
        name='appstore_project_documentation_file'),
]
