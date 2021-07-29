from django.urls import path, re_path

from corehq.apps.registry.views import (
    data_registries,
    accept_registry_invitation,
    reject_registry_invitation,
    manage_registry,
    edit_registry_attr,
    manage_invitations,
    manage_grants,
    delete_registry,
)

urlpatterns = [
    re_path(r'^$', data_registries, name='data_registries'),
    path('accept/', accept_registry_invitation, name='accept_registry_invitation'),
    path('reject/', reject_registry_invitation, name='reject_registry_invitation'),
    path('manage/<slug:registry_slug>/', manage_registry, name='manage_registry'),
    path('edit_registry_attr/<slug:registry_slug>/<slug:attr>/', edit_registry_attr, name='edit_registry_attr'),
    path('manage_invitations/<slug:registry_slug>/', manage_invitations, name='manage_invitations'),
    path('manage_grants/<slug:registry_slug>/', manage_grants, name='manage_grants'),
    path('delete/<slug:registry_slug>/', delete_registry, name='delete_registry'),
]
