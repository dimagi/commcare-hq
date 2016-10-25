from django.conf.urls import include, patterns, url
from .models import GrapevineResource

gvi_resource = GrapevineResource()

urlpatterns = patterns('corehq.messaging.smsbackends.grapevine.views',
    url(r'^api/', include(gvi_resource.urls)),
)
