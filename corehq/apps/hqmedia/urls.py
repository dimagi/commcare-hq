from django.conf.urls import *
from corehq.apps.hqmedia.views import (
    DownloadMultimediaZip,
    ProcessBulkUploadView,
    MultimediaUploadStatusView,
    ViewMultimediaFile,
    ProcessImageFileUploadView,
    ProcessAudioFileUploadView,
    ProcessVideoFileUploadView,
    ProcessLogoFileUploadView,
    ProcessTextFileUploadView,
    RemoveLogoView,
)

urlpatterns = patterns('corehq.apps.hqmedia.views',
    url(r'^file/(?P<media_type>[\w\-]+)/(?P<doc_id>[\w\-]+)/(.+)?$',
        ViewMultimediaFile.as_view(), name=ViewMultimediaFile.name),
    url(r'^upload_status/$', MultimediaUploadStatusView.as_view(), name=MultimediaUploadStatusView.name)
)

application_urls = patterns('corehq.apps.hqmedia.views',
    url(r'^uploaded/bulk/$', ProcessBulkUploadView.as_view(), name=ProcessBulkUploadView.name),
    url(r'^uploaded/image/$', ProcessImageFileUploadView.as_view(), name=ProcessImageFileUploadView.name),
    url(r'^uploaded/app_logo/(?P<logo_name>[\w\-]+)/$', ProcessLogoFileUploadView.as_view(),
        name=ProcessLogoFileUploadView.name),
    url(r'^uploaded/audio/$', ProcessAudioFileUploadView.as_view(), name=ProcessAudioFileUploadView.name),
    url(r'^uploaded/video/$', ProcessVideoFileUploadView.as_view(), name=ProcessVideoFileUploadView.name),
    url(r'^uploaded/text/$', ProcessTextFileUploadView.as_view(),
        name=ProcessTextFileUploadView.name),
    url(r'^remove_logo/$', RemoveLogoView.as_view(), name=RemoveLogoView.name),
)

download_urls = patterns('corehq.apps.hqmedia.views',
                         url(r'^commcare.zip$', DownloadMultimediaZip.as_view(), name=DownloadMultimediaZip.name),
                         )
