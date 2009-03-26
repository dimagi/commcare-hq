from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$', 'djflot.views.summary_trend'),
    
)
