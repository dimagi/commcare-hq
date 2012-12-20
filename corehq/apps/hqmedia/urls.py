from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqmedia.views',
    url(r'^file/(?P<media_type>[\w\-]+)/(?P<doc_id>[\w\-]+)/(foo.mp3)?(foo.wav)?$', "download_media", name="hqmedia_download"),
)

application_urls = patterns('corehq.apps.hqmedia.views',
    url(r'^upload/$', "upload", name="hqmedia_bulk_upload"),
    url(r'^uploaded/$', "uploaded", name="hqmedia_handle_uploaded"),
    url(r'^map/$', "media_map", name="hqmedia_references"),
    url(r'^search/$', 'search_for_media', name='hqmedia_search'),
    url(r'^choose/$', 'choose_media', name='hqmedia_choose_media'),
    url(r'^urls/$', 'media_urls', name='hqmedia_media_urls'),
    url(r'^preview/$', 'media_map', name='emulator_root_url'), # hack so that we can reverse() and get back the root preview url for use in the emulator
    url(r'^preview/(?P<file_path>.+)', 'media_from_path', name='media_from_path'),
)
