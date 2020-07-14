from django.conf.urls import url

from corehq.apps.widget.views import dialer_view

urlpatterns = [
    url(r'dialer/$', dialer_view, name="dialer_view"),
]
