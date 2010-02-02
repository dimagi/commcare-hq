from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^backups/restore/(?P<code_id>\d+)$', 'backups.views.restore', name='restore'),
)
