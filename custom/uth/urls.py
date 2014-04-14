from django.conf.urls.defaults import *

from custom.uth.views import ImageUploadView

urlpatterns = patterns(
    'custom.uth.views',
    url(r'^upload_images/$', ImageUploadView.as_view(), name=ImageUploadView.urlname)
)
