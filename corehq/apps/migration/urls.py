from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('corehq.apps.migration.views',
    (r'^$',  'post'),
    url(r'^2012-07/$', 'resubmit_for_users', name='migration_resubmit_for_users'),
    url(r'^2012-07/forward/$', 'forward', name='migration_forward')
)