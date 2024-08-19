from django.urls import re_path as url
from corehq.apps.prototype.views import example

urlpatterns = [
    url(r'^example/$', example.knockout_pagination,
        name='prototype_example_knockout_pagination'),
    url(r'^webpack/pagination/$', example.knockout_pagination_webpack,
        name='prototype_example_knockout_pagination_webpack'),
    url(r'^webpack/again/$', example.another_webpack_test,
        name='prototype_another_webpack_test'),
    url(r'^webpack/bootstrap3/$', example.bootstrap3_tests_webpack,
        name='prototype_bootstrap3_tests_webpack'),
    url(r'^example/data/$', example.example_paginated_data,
        name='prototype_example_paginated_data'),
]
