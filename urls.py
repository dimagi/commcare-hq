
from django.conf.urls.defaults import *

urlpatterns = patterns('',
    url(r'^downloader/(?P<download_id>[0-9a-fA-Z]{25,32})$', 'downloader.downloaderviews.retrieve_download', name='retrieve_download'),
    url(r'^downloader/ajax/(?P<download_id>[0-9a-fA-Z]{25,32})$', 'downloader.downloaderviews.ajax_job_poll', name='ajax_job_poll'),
)