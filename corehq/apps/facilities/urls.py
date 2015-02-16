from django.conf.urls import patterns, url

settings_urls = patterns('corehq.apps.facilities.views',
    url(r'^$', 'default'),
    url(r'^registries/$', 'list_registries'),
    url(r'^registries/new/$', 'add_view_or_update_registry',
        name='add_registry'),
    url(r'^registries/(?P<id>[\w-]+)?$', 'add_view_or_update_registry',
        name="view_or_update_registry"),
    url(r'^registries/(?P<id>[\w-]+)/sync/(?P<strategy>[\w]+)$',
        'sync_registry', name="sync_registry"),
    url(r'^registries/(?P<id>[\w-]+)/delete/$', 'delete_registry',
        name="delete_registry"),
    url(r'^facilities/(?P<registry_id>[\w-]+)?$', 'list_facilities',
        name="list_facilities"),
    url(r'^facility/(?P<id>[\w-]+)$', 'view_or_update_facility',
        name="view_or_update_facility"),
    url(r'^facility/(?P<id>[\w-]+)/delete/$', 'delete_facility'),

    # todo: create facility?
)
