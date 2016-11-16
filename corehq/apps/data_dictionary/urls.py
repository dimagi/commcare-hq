from django.conf.urls import url
from corehq.apps.data_dictionary.views import (
    data_dictionary_json,
    generate_data_dictionary,
    DataDictionaryView,
)

urlpatterns = [
    url(r"^generate/$", generate_data_dictionary),
    url(r"^json/$", data_dictionary_json),
    url(r"^$", DataDictionaryView.as_view(), name=DataDictionaryView.urlname)
]
