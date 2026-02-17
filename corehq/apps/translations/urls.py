from django.urls import re_path as url

from corehq.apps.translations.integrations.transifex.views import (
    ConvertTranslations,
    DownloadTranslations,
    delete_translation_blacklist,
)

urlpatterns = [
    url(r'^convert/$', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
    url(r'^blacklist_translations/delete/(?P<pk>[0-9]+)/$', delete_translation_blacklist,
        name='delete_translation_blacklist'),
    url(r'^dl/', DownloadTranslations.as_view(),
        name='download_translations'),
]
