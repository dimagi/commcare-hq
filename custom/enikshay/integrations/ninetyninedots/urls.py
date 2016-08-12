from django.conf.urls import patterns, url

urlpatterns = patterns(
    'custom.enikshay.integrations.ninetyninedots.views',
    url(r'^update_patient_adherence$', 'update_patient_adherence'),
    url(r'^update_adherence_confidence$', 'update_adherence_confidence'),
    url(r'^update_default_confidence$', 'update_default_confidence'),
)
