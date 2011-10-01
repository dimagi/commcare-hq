from django.conf.urls.defaults import *

urlpatterns = patterns('',         
    url(r'^in/$', 'corehq.apps.unicel.views.incoming'),
)

