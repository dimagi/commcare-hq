from django.urls import re_path as url

from .views import export_all

urlpatterns = [
    url(r'^auditor/export/$', export_all, name='export_all_audits'),
]
