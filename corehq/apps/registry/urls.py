from django.conf.urls import url

from corehq.apps.registry.views import (
    data_registries,
    accept_registry_invitation,
    reject_registry_invitation
)

urlpatterns = [
    url(r'^$', data_registries, name='data_registries'),
    url(r'^accept$', accept_registry_invitation, name='accept_registry_invitation'),
    url(r'^reject$', reject_registry_invitation, name='reject_registry_invitation'),
]
