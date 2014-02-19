from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^model/$', 'couchexport.views.export_data', name='model_download_excel'),
    url(r'^async/$', 'couchexport.views.export_data_async', name='export_data_async'),
    url(r'^exportgroup/(?P<group_id>[\w-]+)/$', 'couchexport.views.view_export_group',
        name='couchexport_view_export_group'),
    url(r'^saved/(?P<export_id>[\w-]+)/$', 'couchexport.views.download_saved_export',
        name='couchexport_download_saved_export'),
)
