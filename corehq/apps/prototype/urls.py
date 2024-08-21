from django.urls import re_path as url
from corehq.apps.prototype.views import example

urlpatterns = [
    url(r'^example/$', example.knockout_pagination,
        name='prototype_example_knockout_pagination'),
    url(r'^example/data/$', example.example_paginated_data,
        name='prototype_example_paginated_data'),
]
