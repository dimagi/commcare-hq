from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from .views import (
    ConvertTranslations,
    PullResource,
)

urlpatterns = [
    url(r'^convert/$', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
    url(r'^pull_resource/$', PullResource.as_view(),
        name=PullResource.urlname),
]
