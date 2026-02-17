from django.urls import re_path as url

from corehq.apps.translations.integrations.transifex.views import (
    ConvertTranslations,
)

urlpatterns = [
    url(r'^convert/$', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
]
