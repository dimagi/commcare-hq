from django.urls import re_path as url

from corehq.apps.public_webforms.views import ManagePublicWebformsView

urlpatterns = [
    url(r'^$', ManagePublicWebformsView.as_view(), name=ManagePublicWebformsView.urlname),
]
