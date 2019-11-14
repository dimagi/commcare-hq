from django.conf.urls import url, include
from corehq.apps.api.urls import CommCareHqApi
from custom.ewsghana.resources.v0_1 import EWSLocationResource
from custom.ewsghana.views import (
    DashboardPageView, configure_in_charge,
    inventory_management, stockouts_product,
    non_administrative_locations_for_select2,
)

hq_api = CommCareHqApi(api_name='v0.3')
hq_api.register(EWSLocationResource())

urlpatterns = [
    url(r'^configure_in_charge/$', configure_in_charge, name='configure_in_charge'),
    url(r'^inventory_managment/$', inventory_management, name='inventory_managment'),
    url(r'^stockouts_product/$', stockouts_product, name='stockouts_product'),
    url(r'^', include(hq_api.urls)),
    url(r'^non_administrative_locations/$', non_administrative_locations_for_select2,
        name='non_administrative_locations_for_select2'),
    url(r'^dashboard_page/$', DashboardPageView.as_view(permanent=True), name='dashboard_page'),
]
