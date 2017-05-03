from django.conf.urls import url
from corehq.apps.motech.openmrs import views

urlpatterns = [
    # concepts
    url(r'^rest/concept/$',
        views.all_openmrs_concepts,
        name='all_openmrs_concepts'),
    url(r'^rest/concept/search/$',
        views.concept_search,
        name='openmrs_concept_search'),
    url(r'^rest/concept/sync/$',
        views.sync_concepts,
        name='openmrs_sync_concepts'),
]
