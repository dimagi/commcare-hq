from django.urls import re_path as url
from corehq.apps.prototype.views import example
from corehq.apps.prototype.views import webpack

urlpatterns = [
    url(r'^webpack/b5_amd/$', webpack.bootstrap5_amd_example,
        name='webpack_bootstrap5_amd_example'),
    url(r'^webpack/b3_amd/$', webpack.bootstrap3_amd_example,
        name='webpack_bootstrap3_amd_example'),
    url(r'^webpack/pagination/$', webpack.knockout_pagination,
        name='webpack_knockout_pagination'),
    url(r'^example/$', example.knockout_pagination,
        name='prototype_example_knockout_pagination'),
    url(r'^example/data/$', example.example_paginated_data,
        name='prototype_example_paginated_data'),
    url(r'^example/today.ics/$', example.generate_ics,
        name='prototype_example_ics')
]
