from django.conf.urls import url

from custom.icds.data_management.views import (
    DataManagementView,
    paginate_data_management_requests,
)

urlpatterns = [
    url(r'^data_management', DataManagementView.as_view(), name=DataManagementView.urlname),
    url(r'paginate_data_management_requests', paginate_data_management_requests,
        name='paginate_data_management_requests'),
]
