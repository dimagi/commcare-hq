from django.conf.urls import patterns, url

urlpatterns = patterns(
    'custom.enikshay.integrations.ninetyninedots.views',
    url(r'^update_patient_adherence$', 'update_patient_adherence'),
)
