from django.urls import re_path as url
from django.views.generic import RedirectView

from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.views import (
    FixtureUploadStatusView,
    UploadItemLists,
    download_item_lists,
    fixture_api_upload_status,
    fixture_metadata,
    fixture_upload_job_poll,
    update_tables,
    upload_fixture_api,
)
from corehq.apps.hqwebapp.decorators import waf_allow

urlpatterns = [
    url(r'^fixapi/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        fixture_api_upload_status, name='fixture_api_status'),
    url(r'^fixapi/', upload_fixture_api),
    url(r'^metadata/$', fixture_metadata, name='fixture_metadata'),
    url(r'^$', RedirectView.as_view(url='edit_lookup_tables', permanent=True), name='edit_lookup_tables'),
    FixtureInterfaceDispatcher.url_pattern(),
    url(r'^edit_lookup_tables/download/$', download_item_lists, name="download_fixtures"),
    url(r'^edit_lookup_tables/upload/$', waf_allow('XSS_BODY')(UploadItemLists.as_view()), name='upload_fixtures'),
    url(r'^edit_lookup_tables/update-tables/(?P<data_type_id>[\w-]+)?$', update_tables,
        name='update_lookup_tables'),

    # upload status
    url(r'^upload/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        FixtureUploadStatusView.as_view(),
        name=FixtureUploadStatusView.urlname),
    url(r'^upload/status/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        fixture_upload_job_poll, name='fixture_upload_job_poll'),
]
