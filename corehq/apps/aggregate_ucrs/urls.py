from __future__ import absolute_import, unicode_literals
from django.conf.urls import url
from . import views

# these are included by the userreports urls
urlpatterns = [
    url(r'^view/(?P<table_id>[\w-]+)/$', views.AggregateUCRView.as_view(),
        name=views.AggregateUCRView.urlname),
]
