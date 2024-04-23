from django.urls import re_path as url

from corehq.apps.hqmedia.views import (
    BulkUploadMultimediaView,
    DownloadMultimediaZip,
    ManageMultimediaPathsView,
    MultimediaAudioTranslatorFileView,
    MultimediaReferencesView,
    MultimediaTranslationsCoverageView,
    MultimediaUploadStatusView,
    ProcessAudioFileUploadView,
    ProcessBulkUploadView,
    ProcessDetailPrintTemplateUploadView,
    ProcessImageFileUploadView,
    ProcessLogoFileUploadView,
    ProcessTextFileUploadView,
    ProcessVideoFileUploadView,
    RemoveDetailPrintTemplateView,
    RemoveLogoView,
    ViewMultimediaFile,
    download_multimedia_paths,
)
from corehq.apps.hqwebapp.decorators import waf_allow

urlpatterns = [
    url(r'^file/(?P<media_type>[\w\-]+)/(?P<doc_id>[\w\-]+)/(.+)?$',
        ViewMultimediaFile.as_view(), name=ViewMultimediaFile.urlname),
    url(r'^upload_status/$', MultimediaUploadStatusView.as_view(), name=MultimediaUploadStatusView.urlname)
]

application_urls = [
    url(r'^upload/$', BulkUploadMultimediaView.as_view(), name=BulkUploadMultimediaView.urlname),
    url(r'^paths/$', ManageMultimediaPathsView.as_view(), name=ManageMultimediaPathsView.urlname),
    url(r'^paths/download/$', download_multimedia_paths, name='download_multimedia_paths'),
    url(r'^audio_translator_file/$', MultimediaAudioTranslatorFileView.as_view(),
        name=MultimediaAudioTranslatorFileView.urlname),
    url(r'^translations/$', MultimediaTranslationsCoverageView.as_view(),
        name=MultimediaTranslationsCoverageView.urlname),
    url(r'^uploaded/bulk/$', ProcessBulkUploadView.as_view(), name=ProcessBulkUploadView.urlname),
    url(r'^uploaded/image/$', waf_allow('XSS_BODY')(ProcessImageFileUploadView.as_view()),
        name=ProcessImageFileUploadView.urlname),
    url(r'^uploaded/app_logo/(?P<logo_name>[\w\-]+)/$', waf_allow('XSS_BODY')(ProcessLogoFileUploadView.as_view()),
        name=ProcessLogoFileUploadView.urlname),
    url(r'^uploaded/audio/$', waf_allow('XSS_BODY')(ProcessAudioFileUploadView.as_view()),
        name=ProcessAudioFileUploadView.urlname),
    url(r'^uploaded/video/$', waf_allow('XSS_BODY')(ProcessVideoFileUploadView.as_view()),
        name=ProcessVideoFileUploadView.urlname),
    url(r'^uploaded/text/$', ProcessTextFileUploadView.as_view(),
        name=ProcessTextFileUploadView.urlname),
    url(r'^uploaded/detail_print/(?P<module_unique_id>[\w-]+)/$', ProcessDetailPrintTemplateUploadView.as_view(),
        name=ProcessDetailPrintTemplateUploadView.urlname),
    url(r'^remove_logo/$', RemoveLogoView.as_view(), name=RemoveLogoView.urlname),
    url(r'^remove_print_template/$', RemoveDetailPrintTemplateView.as_view(),
        name=RemoveDetailPrintTemplateView.urlname),
    url(r'^map/$', MultimediaReferencesView.as_view(), name=MultimediaReferencesView.urlname),
]

download_urls = [
    url(r'^commcare.zip$', DownloadMultimediaZip.as_view(), name=DownloadMultimediaZip.urlname),
]
