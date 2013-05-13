from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^post/?$', 'couchforms.views.post', name='xform_post'),
    url(r'^download/(?P<instance_id>[\w_-]+)/(?P<attachment>[\w._-]+)?$',
        'couchforms.views.download_attachment', name='xform_attachment'),
)
