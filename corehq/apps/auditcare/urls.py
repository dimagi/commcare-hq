from django.conf.urls import url

from .views import audited_views, export_all

urlpatterns = [
    url(r'^auditor/export/$', export_all, name='export_all_audits'),
    url(r'^auditor/views/$', audited_views, name='audit_views'),
]
