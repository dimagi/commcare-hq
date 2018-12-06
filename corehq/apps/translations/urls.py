from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf.urls import url

from corehq.apps.translations.integrations.transifex.views import (
    ConvertTranslations,
    PullResource,
    AppTranslations,
)

urlpatterns = [
    url(r'^convert/$', ConvertTranslations.as_view(),
        name=ConvertTranslations.urlname),
    url(r'^pull_resource/$', PullResource.as_view(),
        name=PullResource.urlname),
    url(r'^translations/apps/', AppTranslations.as_view(),
        name='app_translations'),
]
