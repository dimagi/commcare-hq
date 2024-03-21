from django.urls import re_path as url

from . import views

# these are included by the userreports urls
urlpatterns = [
    url(r'^view/(?P<table_id>[\w-]+)/$', views.AggregateUCRView.as_view(),
        name=views.AggregateUCRView.urlname),
    url(r'^preview/(?P<table_id>[\w-]+)/$', views.PreviewAggregateUCRView.as_view(),
        name=views.PreviewAggregateUCRView.urlname),
    url(r'^export/(?P<table_id>[\w-]+)/$', views.export_aggregate_ucr,
        name='export_aggregate_ucr'),
    url(r'^rebuild/(?P<table_id>[\w-]+)/$', views.rebuild_aggregate_ucr,
        name='rebuild_aggregate_ucr'),

]
