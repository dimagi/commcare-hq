from django.urls import path

from .views import consumer_form_reference, consumer_form, consumer_form_with_link

app_name = 'consumer_forms'

urlpatterns = [
    path("reference/<slug:link_id>/", consumer_form_reference, name='consumer_form_reference'),
    path("s/<slug:form_id>/", consumer_form, name='consumer_form'),
    path("s/<slug:form_id>/<slug:link_id>/", consumer_form_with_link, name='consumer_form_with_link'),
]
