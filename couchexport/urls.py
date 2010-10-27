from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^model/$', 'couchexport.views.export_data', name='model_download_excel'),
)
