from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.hqmedia.views import (
    DownloadMultimediaZip,
    BulkUploadMultimediaView,
    ProcessBulkUploadView,
    MultimediaUploadStatusView,
    ViewMultimediaFile,
    MultimediaReferencesView,
    ProcessImageFileUploadView,
    ProcessAudioFileUploadView,
    ProcessVideoFileUploadView,
    ProcessLogoFileUploadView,
    ProcessTextFileUploadView,
    ProcessDetailPrintTemplateUploadView,
    RemoveLogoView,
    RemoveDetailPrintTemplateView,
)

urlpatterns = [
    url(r'^file/(?P<media_type>[\w\-]+)/(?P<doc_id>[\w\-]+)/(.+)?$',
        ViewMultimediaFile.as_view(), name=ViewMultimediaFile.name),
    url(r'^upload_status/$', MultimediaUploadStatusView.as_view(), name=MultimediaUploadStatusView.name)
]

application_urls = [
    url(r'^upload/$', BulkUploadMultimediaView.as_view(), name=BulkUploadMultimediaView.name),
    url(r'^uploaded/bulk/$', ProcessBulkUploadView.as_view(), name=ProcessBulkUploadView.name),
    url(r'^uploaded/image/$', ProcessImageFileUploadView.as_view(), name=ProcessImageFileUploadView.name),
    url(r'^uploaded/app_logo/(?P<logo_name>[\w\-]+)/$', ProcessLogoFileUploadView.as_view(),
        name=ProcessLogoFileUploadView.name),
    url(r'^uploaded/audio/$', ProcessAudioFileUploadView.as_view(), name=ProcessAudioFileUploadView.name),
    url(r'^uploaded/video/$', ProcessVideoFileUploadView.as_view(), name=ProcessVideoFileUploadView.name),
    url(r'^uploaded/text/$', ProcessTextFileUploadView.as_view(),
        name=ProcessTextFileUploadView.name),
    url(r'^uploaded/detail_print/(?P<module_unique_id>[\w-]+)/$', ProcessDetailPrintTemplateUploadView.as_view(),
        name=ProcessDetailPrintTemplateUploadView.name),
    url(r'^remove_logo/$', RemoveLogoView.as_view(), name=RemoveLogoView.name),
    url(r'^remove_print_template/$', RemoveDetailPrintTemplateView.as_view(),
        name=RemoveDetailPrintTemplateView.name),
    url(r'^map/$', MultimediaReferencesView.as_view(), name=MultimediaReferencesView.name),
]

download_urls = [
    url(r'^commcare.zip$', DownloadMultimediaZip.as_view(), name=DownloadMultimediaZip.name),
]
