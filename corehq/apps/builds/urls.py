from django.conf.urls import patterns, url
from .views import EditMenuView

urlpatterns = patterns('corehq.apps.builds.views',
    url(r'^edit_menu/$', EditMenuView.as_view(), name=EditMenuView.urlname),
    (r'^import/$', 'import_build'),
    (r'^post/$', 'post'),
    (r'^(?P<version>.+)/(?P<build_number>\d+)/(?P<path>.+)$', "get"),
    (r'^$', 'get_all'),
)
