from django.conf.urls import url

from custom.icds_reports.views import TableauView, DashboardView

urlpatterns = [
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', TableauView.as_view(), name='icds_tableau'),
    url(r'^icds_dashboard/', DashboardView.as_view(), name='icds_dashboard'),
]
