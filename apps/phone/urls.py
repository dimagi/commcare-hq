from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^backups/(?P<backup_id>\d+)/?$', 'phone.views.restore', name='restore'),
)
