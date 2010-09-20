from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'post', 'new_xforms.views.post'),
    (r'download_excel', 'couchforms.views.download_excel'),
    (r'', 'new_xforms.views.dashboard'),
)