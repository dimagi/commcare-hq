from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    (r'^photos/?$', 'photos.views.recent'),
    (r'^photo/(?P<photo_id>\d+)/?$', 'photos.views.show'),
    (r'^data/photos/(?P<path>.*)$',  'django.views.static.serve', {"document_root": 'data/photos/'}),
)
