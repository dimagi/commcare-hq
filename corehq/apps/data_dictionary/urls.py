from django.conf.urls import url
from corehq.apps.data_dictionary.views import (
    data_dictionary_json,
    generate_data_dictionary,
    update_case_property_description,
    DataDictionaryView,
)

urlpatterns = [
    url(r"^generate/$", generate_data_dictionary),
    url(r"^json/$", data_dictionary_json, name='data_dictionary_json'),
    url(r"^json/?(?P<case_type_name>\w+)/?$", data_dictionary_json, name='case_type_dictionary_json'),
    url(r"^update_case_property_description/$",
        update_case_property_description,
        name='update_case_property_description'),
    url(r"^$", DataDictionaryView.as_view(), name=DataDictionaryView.urlname)
]
