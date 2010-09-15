from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^model/$', 'couchexport.views.download_model', name='model_download_excel'),
)
