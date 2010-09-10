from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^download_excel/$', 'couchforms.views.download_excel', name='xform_download_excel'),
    url(r'^post/$', 'couchforms.views.post', name='xform_post'),
)
