from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.users.views',
    (r'^$', 'users'),
)