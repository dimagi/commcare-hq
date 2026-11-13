from django.urls import re_path as url

from .views import EditMenuView, get_all, import_build, post

urlpatterns = [
    url(r'^edit_menu/$', EditMenuView.as_view(), name=EditMenuView.urlname),
    url(r'^import/$', import_build, name='import_build'),
    url(r'^post/$', post),
    url(r'^$', get_all),
]
