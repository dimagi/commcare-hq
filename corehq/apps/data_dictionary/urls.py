from django.conf.urls import re_path as url

from corehq.apps.data_dictionary.views import (
    DataDictionaryView,
    ExportDataDictionaryView,
    UploadDataDictionaryView,
    data_dictionary_json,
    update_case_property,
    update_case_property_description,
    create_case_type,
    deprecate_or_restore_case_type,
    delete_case_type,
)
from corehq.apps.hqwebapp.decorators import waf_allow

urlpatterns = [
    url(r"^json/$", data_dictionary_json, name='data_dictionary_json'),
    url(r"^json/?(?P<case_type_name>\w+)/?$", data_dictionary_json, name='case_type_dictionary_json'),
    url(r"^create_case_type/$", create_case_type, name='create_case_type'),
    url(r"^deprecate_or_restore_case_type/(?P<case_type_name>[\w-]+)/$", deprecate_or_restore_case_type,
        name='deprecate_or_restore_case_type'),
    url(r"^delete_case_type/(?P<case_type_name>[\w-]+)/$", delete_case_type, name='delete_case_type'),
    url(r"^update_case_property/$", update_case_property, name='update_case_property'),
    url(r"^update_case_property_description/$", update_case_property_description,
        name='update_property_description'),
    url(r"^export/$", ExportDataDictionaryView.as_view(), name=ExportDataDictionaryView.urlname),
    url(r"^$", DataDictionaryView.as_view(), name=DataDictionaryView.urlname),
    url(r"^import$", waf_allow('XSS_BODY')(UploadDataDictionaryView.as_view()),
        name=UploadDataDictionaryView.urlname),
]
