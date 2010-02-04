from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^backups/(?P<backup_id>\d+)/?$', 'backups.views.restore', name='restore'),
)
