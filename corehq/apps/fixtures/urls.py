from corehq.apps.fixtures.views import UploadItemLists
from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
from corehq.apps.fixtures.interface import FixtureEditInterface
from django.conf.urls.defaults import patterns, url
from django.core.urlresolvers import reverse_lazy
from django.views.generic import RedirectView

urlpatterns = patterns('corehq.apps.fixtures.views',
    url(r'^fixapi/', 'upload_fixture_api'),
    url(r'^$', RedirectView.as_view(url='edit_lookup_tables')),
    FixtureInterfaceDispatcher.url_pattern(),
    url(r'^edit_lookup_tables/data-types/$', 'tables', name='fixture_data_types'),
    url(r'^edit_lookup_tables/download/$', 'download_item_lists', name="download_fixtures"),
    url(r'^edit_lookup_tables/upload/$', UploadItemLists.as_view(), name='upload_fixtures'),
    url(r'^edit_lookup_tables/file/$', 'download_file', name="download_fixture_file"),
    url(r'^edit_lookup_tables/update-tables/(?P<data_type_id>[\w-]+)?$', 'update_tables', name='update_lookup_tables')
)