from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqmedia.views',
    url(r'^file/(?P<media_type>[\w\-]+)/(?P<doc_id>[\w\-]+)/(foo.mp3)?$', "download_media", name="hqmedia_download"),
)

application_urls = patterns('corehq.apps.hqmedia.views',
    url(r'^upload/$', "upload", name="hqmedia_bulk_upload"),
    url(r'^uploaded/$', "uploaded", name="hqmedia_handle_uploaded")
)