from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.migration.views',
    (r'^$',  'post'),
)