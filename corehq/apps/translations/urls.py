from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from .views import (
    ConvertTranslations,
    PullResource,
)

translations_urls = [
    url(r'^convert_translations/$', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
    url(r'^pull_resource/$', PullResource.as_view(),
        name=PullResource.urlname),
    url(r'^', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
]
