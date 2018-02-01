from __future__ import absolute_import
from django.conf.urls import url

from corehq.apps.linked_domain.views import toggles_and_previews, custom_data_models, user_roles

urlpatterns = [
    url(r'^toggles/$', toggles_and_previews),
    url(r'^custom_data_models/$', custom_data_models),
    url(r'^user_roles/$', user_roles),
]
