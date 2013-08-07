from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('corehq.apps.prescriptions.views',
    url(r'^all/$', 'all_prescriptions', name='all_prescriptions'),
    url(r'^add/$', 'add_prescription', name='add_prescription'),
    url(r'^edit/(?P<prescription_id>[\w-]+)/$', 'add_prescription', name='edit_prescription'),
    url(r'^delete/(?P<prescription_id>[\w-]+)/$', 'delete_prescription', name='delete_prescription'),
)