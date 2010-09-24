from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'post', 'corehq.apps.new_xforms.views.post'),
    (r'download_excel', 'couchforms.views.download_excel'),
    (r'', 'corehq.apps.new_xforms.views.dashboard'),
)