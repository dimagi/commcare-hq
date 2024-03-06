from django.urls import re_path as url

from corehq.apps.translations.integrations.transifex.views import (
    AppTranslations,
    BlacklistTranslations,
    ConvertTranslations,
    DownloadTranslations,
    MigrateTransifexProject,
    PullResource,
    delete_translation_blacklist,
)

urlpatterns = [
    url(r'^convert/$', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
    url(r'^pull_resource/$', PullResource.as_view(),
        name=PullResource.urlname),
    url(r'^blacklist_translations/$', BlacklistTranslations.as_view(),
        name=BlacklistTranslations.urlname),
    url(r'^blacklist_translations/delete/(?P<pk>[0-9]+)/$', delete_translation_blacklist,
        name='delete_translation_blacklist'),
    url(r'^translations/apps/', AppTranslations.as_view(),
        name='app_translations'),
    url(r'^dl/', DownloadTranslations.as_view(),
        name='download_translations'),
    url(r'^migrate/$', MigrateTransifexProject.as_view(),
        name='migrate_transifex_project'),
]
