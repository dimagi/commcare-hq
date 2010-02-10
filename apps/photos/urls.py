from django.conf.urls.defaults import *
import settings

image_path = settings.RAPIDSMS_APPS['photos']['image_path']

urlpatterns = patterns('',                       
    (r'^photos/?$', 'photos.views.recent'),
    (r'^photo/(?P<photo_id>\d+)/?$', 'photos.views.show'),
    (r'^%s/(?P<path>.*)$' % image_path,  'django.views.static.serve', {"document_root": '%s/' % image_path}),
    (r'^photo/comments/', include('django.contrib.comments.urls')),
    # (r'^photos/populate/?$', 'photos.views.populate'), # remove this once testing is done
    (r'^photos/import/?$', 'photos.views.import_photos'), # and this too
)
