from django.conf.urls import url
from custom.zipline.views import ZiplineOrderStatusView

urlpatterns = [
    url(r'^order/status/$', ZiplineOrderStatusView.as_view(), name=ZiplineOrderStatusView.urlname),
]
