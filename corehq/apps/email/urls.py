from django.conf.urls import re_path as url

from corehq.apps.email.views import DomainEmailGatewayListView, AddDomainEmailGatewayView, EditDomainEmailGatewayView
from corehq.apps.email.views import default

urlpatterns = [
    url(r'^$', default, name='email_default'),
    url(r'^add_gateway/(?P<hq_api_id>[\w-]+)/$',
        AddDomainEmailGatewayView.as_view(), name=AddDomainEmailGatewayView.urlname
        ),
    url(r'^edit_gateway/(?P<hq_api_id>[\w-]+)/(?P<backend_id>[\w-]+)/$',
        EditDomainEmailGatewayView.as_view(), name=EditDomainEmailGatewayView.urlname
        ),
    url(r'^gateways/$', DomainEmailGatewayListView.as_view(), name=DomainEmailGatewayListView.urlname),
]
