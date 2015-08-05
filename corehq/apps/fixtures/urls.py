from django.conf.urls import url, patterns
from corehq.apps.fixtures.views import UploadItemLists, FixtureUploadStatusView
from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher

from django.views.generic import RedirectView

urlpatterns = patterns('corehq.apps.fixtures.views',
    url(r'^fixapi/', 'upload_fixture_api'),
    url(r'^metadata/$', 'fixture_metadata', name='fixture_metadata'),
    url(r'^$', RedirectView.as_view(url='edit_lookup_tables'), name='edit_lookup_tables'),
    FixtureInterfaceDispatcher.url_pattern(),
    url(r'^edit_lookup_tables/data-types/$', 'tables', name='fixture_data_types'),
    url(r'^edit_lookup_tables/download/$', 'download_item_lists', name="download_fixtures"),
    url(r'^edit_lookup_tables/upload/$', UploadItemLists.as_view(), name='upload_fixtures'),
    url(r'^edit_lookup_tables/file/$', 'download_file', name="download_fixture_file"),
    url(r'^edit_lookup_tables/update-tables/(?P<data_type_id>[\w-]+)?$', 'update_tables', name='update_lookup_tables'),

    # upload status
    url(r'^upload/status/(?P<download_id>[0-9a-fA-Z]{25,32})/$', FixtureUploadStatusView.as_view(),
        name=FixtureUploadStatusView.urlname),
    url(r'^upload/status/poll/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        'fixture_upload_job_poll', name='fixture_upload_job_poll'),
)
