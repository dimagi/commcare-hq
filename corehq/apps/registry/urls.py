from django.urls import path, re_path

from corehq.apps.registry.views import (
    data_registries,
    accept_registry_invitation,
    reject_registry_invitation,
    edit_registry,
    edit_registry_attr,
    manage_registry_participation
)

urlpatterns = [
    re_path(r'^$', data_registries, name='data_registries'),
    path('accept/', accept_registry_invitation, name='accept_registry_invitation'),
    path('reject/', reject_registry_invitation, name='reject_registry_invitation'),
    path('edit/<slug:registry_slug>/', edit_registry, name='edit_registry'),
    path('edit_registry_attr/<slug:registry_slug>/<slug:attr>/', edit_registry_attr, name='edit_registry_attr'),
    path('manage_participation/<slug:registry_slug>/', manage_registry_participation, name='manage_registry_participation'),
]
