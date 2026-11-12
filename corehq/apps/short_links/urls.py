from django.urls import re_path as url

from corehq.apps.short_links.views import follow_short_link

urlpatterns = [
    url(r'^(?P<code>[A-Za-z0-9]{1,32})$', follow_short_link, name='follow_short_link'),
]
