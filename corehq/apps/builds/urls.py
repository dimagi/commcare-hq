from django.conf.urls.defaults import *
from .views import EditMenuView

urlpatterns = patterns('corehq.apps.builds.views',
    (r'^edit_menu/$', EditMenuView.as_view()),
    (r'^import/$', 'import_build'),
    (r'^post/$', 'post'),
    (r'^(?P<version>.+)/(?P<build_number>\d+)/(?P<path>.+)$', "get"),
    (r'^$', 'get_all'),
)
