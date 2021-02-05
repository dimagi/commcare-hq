from django.urls import path

from .views import access_authenticated_link

app_name = 'consumer_forms'

urlpatterns = [
    path("link/<slug:link_id>/", access_authenticated_link, name='generate_data_dictionary'),
]
