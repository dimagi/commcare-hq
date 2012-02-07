from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqmedia.views',
    url(r'^media_data/(?P<media_type>[\w\-]+)/(?P<doc_id>[\w\-]+)/(foo.mp3)?$', "download_media", name="hqmedia_download"),
    url(r'^upload_status/$', "check_upload_progress", name="hqmedia_upload_progress"),
    url(r'^upload_success_cache/$', "check_upload_success", name="hqmedia_upload_success"),
)