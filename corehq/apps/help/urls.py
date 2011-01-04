from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.help.views',
    (r'^(?P<topic>[\w-]+)/$', 'index'),
    (r'^$', 'default'),
)