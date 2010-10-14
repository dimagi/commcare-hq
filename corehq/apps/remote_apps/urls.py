from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.remote_apps.views',
    (r'view/(?P<app_id>\w+)/$',   'app_view'),
    (r'view/$',                 'view'),
)