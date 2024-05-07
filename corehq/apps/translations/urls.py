from django.urls import re_path as url

from corehq.apps.translations.integrations.transifex.views import (
    BlacklistTranslations,
    CreateUpdateTranslations,
    ConvertTranslations,
    DeleteTranslations,
    DownloadTranslations,
    MigrateTransifexProject,
    PullResource,
    PushTranslations,
    PullTranslations,
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
    url(r'^translations/create_update', CreateUpdateTranslations.as_view(),
        name='create_update_translations'),
    url(r'^translations/push', PushTranslations.as_view(),
        name='push_translations'),
    url(r'^translations/pull', PullTranslations.as_view(),
        name='pull_translations'),
    url(r'^translations/delete', DeleteTranslations.as_view(),
        name='delete_translations'),
    url(r'^dl/', DownloadTranslations.as_view(),
        name='download_translations'),
    url(r'^migrate/$', MigrateTransifexProject.as_view(),
        name='migrate_transifex_project'),
]
