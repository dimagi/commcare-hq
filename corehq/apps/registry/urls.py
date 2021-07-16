from django.conf.urls import url

from corehq.apps.registry.views import data_registries

urlpatterns = [
    url(r'^$', data_registries, name='data_registries'),
]
