from django.conf.urls import url
from corehq.motech.views import MotechLogListView, MotechLogDetailView

urlpatterns = [
    url(r'^logs/$', MotechLogListView.as_view(), name=MotechLogListView.urlname),
    url(r'^logs/(?P<pk>\d+)/$', MotechLogDetailView.as_view(), name=MotechLogDetailView.urlname),
]
