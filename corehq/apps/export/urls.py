from django.conf.urls.defaults import *
from corehq.apps.export.views import (CreateCustomFormExportView, CreateCustomCaseExportView,
                                      EditCustomFormExportView, EditCustomCaseExportView,
                                      DeleteCustomExportView)

urlpatterns = patterns(
    'corehq.apps.export.views',
    url(r"^customize/form/$", CreateCustomFormExportView.as_view(), name=CreateCustomFormExportView.name),
    url(r"^customize/case/$", CreateCustomCaseExportView.as_view(), name=CreateCustomCaseExportView.name),
    url(r"^custom/form/(?P<export_id>[\w\-]+)/edit/$", EditCustomFormExportView.as_view(),
        name=EditCustomFormExportView.name),
    url(r"^custom/case/(?P<export_id>[\w\-]+)/edit/$", EditCustomCaseExportView.as_view(),
        name=EditCustomCaseExportView.name),
    url(r"^custom/(?P<export_id>[\w\-]+)/delete/$", DeleteCustomExportView.as_view(), name=DeleteCustomExportView.name),
)
