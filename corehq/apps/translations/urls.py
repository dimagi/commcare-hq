from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from .views import ConvertTranslations

translations_urls = [
    url(r'^convert_translations/$', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
    url(r'^', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
]
