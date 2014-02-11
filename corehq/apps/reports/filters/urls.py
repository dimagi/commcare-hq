from django.conf.urls.defaults import *

from . import api

urlpatterns = patterns('',
    url(r'^emwf_options', api.EmwfOptionsView.as_view(), name='emwf_options'),
)
