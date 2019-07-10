from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from django.views.generic import RedirectView

from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.views import (
    UploadItemLists, FixtureUploadStatusView,
    upload_fixture_api, fixture_metadata, download_item_lists,
    download_file, update_tables, fixture_upload_job_poll,
    fixture_api_upload_status,
)

urlpatterns = [
    url(r'^fixapi/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        fixture_api_upload_status, name='fixture_api_status'),
    url(r'^fixapi/', upload_fixture_api),
    url(r'^metadata/$', fixture_metadata, name='fixture_metadata'),
    url(r'^$', RedirectView.as_view(url='edit_lookup_tables', permanent=True), name='edit_lookup_tables'),
    FixtureInterfaceDispatcher.url_pattern(),
    url(r'^edit_lookup_tables/download/$', download_item_lists, name="download_fixtures"),
    url(r'^edit_lookup_tables/upload/$', UploadItemLists.as_view(), name='upload_fixtures'),
    url(r'^edit_lookup_tables/file/$', download_file, name="download_fixture_file"),
    url(r'^edit_lookup_tables/update-tables/(?P<data_type_id>[\w-]+)?$', update_tables,
        name='update_lookup_tables'),

    # upload status
    url(r'^upload/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        FixtureUploadStatusView.as_view(),
        name=FixtureUploadStatusView.urlname),
    url(r'^upload/status/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        fixture_upload_job_poll, name='fixture_upload_job_poll'),
]
