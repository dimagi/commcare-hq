from django.conf.urls.defaults import *
from corehq.apps.hqmedia.views import (DownloadMultimediaZip, BulkUploadMultimediaView, ProcessBulkUploadView,
                                       MultimediaUploadStatusView, ViewMultimediaFile, MultimediaReferencesView, ProcessImageFileUploadView, ProcessAudioFileUploadView, ProcessVideoFileUploadView)

urlpatterns = patterns('corehq.apps.hqmedia.views',
    url(r'^file/(?P<media_type>[\w\-]+)/(?P<doc_id>[\w\-]+)/(.+)?$',
        ViewMultimediaFile.as_view(), name=ViewMultimediaFile.name),
    url(r'^upload_status/$', MultimediaUploadStatusView.as_view(), name=MultimediaUploadStatusView.name)
)

application_urls = patterns('corehq.apps.hqmedia.views',
    url(r'^upload/$', BulkUploadMultimediaView.as_view(), name=BulkUploadMultimediaView.name),
    url(r'^uploaded/bulk/$', ProcessBulkUploadView.as_view(), name=ProcessBulkUploadView.name),
    url(r'^uploaded/image/$', ProcessImageFileUploadView.as_view(), name=ProcessImageFileUploadView.name),
    url(r'^uploaded/audio/$', ProcessAudioFileUploadView.as_view(), name=ProcessAudioFileUploadView.name),
    url(r'^uploaded/video/$', ProcessVideoFileUploadView.as_view(), name=ProcessVideoFileUploadView.name),
    url(r'^map/$', MultimediaReferencesView.as_view(), name=MultimediaReferencesView.name),
    url(r'^search/$', 'search_for_media', name='hqmedia_search'),
    url(r'^choose/$', 'choose_media', name='hqmedia_choose_media'),
    url(r'^urls/$', 'media_urls', name='hqmedia_media_urls'),
    url(r'^preview/$', MultimediaReferencesView.as_view(), name='emulator_root_url'), # hack so that we can reverse() and get back the root preview url for use in the emulator
    url(r'^preview/(?P<file_path>.+)', 'media_from_path', name='media_from_path'),
)

download_urls = patterns('corehq.apps.hqmedia.views',
                         url(r'^commcare.zip$', DownloadMultimediaZip.as_view(), name=DownloadMultimediaZip.name),
                         )
