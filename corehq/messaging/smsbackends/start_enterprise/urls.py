from django.conf.urls import url
from corehq.messaging.smsbackends.start_enterprise.views import StartEnterpriseDeliveryReceiptView


urlpatterns = [
    url(r'^dlr/(?P<api_key>[\w-]+)/$', StartEnterpriseDeliveryReceiptView.as_view(),
        name=StartEnterpriseDeliveryReceiptView.urlname),
]
