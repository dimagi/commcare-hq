from django.conf.urls import *

urlpatterns = patterns('',         
    url(r'^in/$', 'corehq.apps.unicel.views.incoming'),
)

