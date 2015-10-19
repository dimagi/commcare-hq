from django.conf.urls import *

urlpatterns = patterns('',
    url(r'^download/(?P<instance_id>[\w_-]+)/(?P<attachment>[\w._-]+)?$',
        'couchforms.views.download_attachment', name='xform_attachment'),
)
