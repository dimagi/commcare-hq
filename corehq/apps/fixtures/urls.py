from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('corehq.apps.fixtures.views',
    url(r'^data-types/(?P<data_type_id>[\w-]+)?', 'data_types', name='fixture_data_types'),
    url(r'^data-items/(?P<data_type_id>[\w-]+)/(?P<data_item_id>[\w-]+)?', 'data_items', name='fixture_data_items'),
    url(r'^$', 'view', name='fixture_view'),
)