from django.conf.urls import url

from custom.icds_reports.views import tableau

urlpatterns = [
    url(r'^tableau/(?P<workbook>\w+)/(?P<worksheet>\w+)$', tableau, name='icds_tableau'),
]
