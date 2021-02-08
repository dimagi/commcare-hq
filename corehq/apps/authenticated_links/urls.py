from django.urls import path

from .views import access_authenticated_link

app_name = 'authenticated_links'

urlpatterns = [
    path("l/<slug:link_id>/", access_authenticated_link, name='access_authenticated_link'),
]
