from django.conf.urls import url

from custom.icds.data_management.views import DataManagementView

urlpatterns = [
    url(r'^data_management', DataManagementView.as_view(), name=DataManagementView.urlname)
]
