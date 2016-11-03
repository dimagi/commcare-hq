from django.conf.urls import url

from corehq.apps.zapier.views import SubscribeView, UnsubscribeView

urlpatterns = [
    url(r'^subscribe/$', SubscribeView.as_view(), name=SubscribeView.urlname),
    url(r'^unsubscribe/$', UnsubscribeView.as_view(), name=UnsubscribeView.urlname)
]
