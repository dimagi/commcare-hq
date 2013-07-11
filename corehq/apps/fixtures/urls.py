from corehq.apps.fixtures.views import UploadItemLists
from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('corehq.apps.fixtures.views',
    url(r'^data-types/(?P<data_type_id>[\w-]+)?$', 'data_types', name='fixture_data_types'),
    url(r'^data-items/(?P<data_type_id>[\w-]+)/(?P<data_item_id>[\w-]+)?$', 'data_items', name='fixture_data_items'),
    url(r'^data-items/(?P<data_type_id>[\w-]+)/(?P<data_item_id>[\w-]+)/groups/(?P<group_id>[\w-]+)$', 'data_item_groups'),
    url(r'^data-items/(?P<data_type_id>[\w-]+)/(?P<data_item_id>[\w-]+)/users/(?P<user_id>[\w-]+)$', 'data_item_users'),
    url(r'^$', 'view', name='fixture_view'),
    url(r'^groups/$', 'groups'),
    url(r'^users/$', 'users'),
    url(r'^item-lists/upload/$', UploadItemLists.as_view(), name='upload_fixtures'),
    url(r'^fixapi/', 'upload_fixture_api'),
    url(r'^item-lists/download/$', 'download_item_lists', name="download_fixtures"),
)