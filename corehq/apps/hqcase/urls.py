from django.conf.urls import url

from corehq.apps.hqcase.views import (
    ExplodeCasesView,
    bulk_update_cases,
    create_case,
    update_case,
)

urlpatterns = [
    url(r'^api/create_case/$', create_case, name='create_case'),
    url(r'^api/update_case/(?P<case_id>[\w-]+)/$', update_case, name='update_case'),
    url(r'^api/bulk_update_cases/$', bulk_update_cases, name='bulk_update_cases'),

    # for load testing
    url(r'explode/', ExplodeCasesView.as_view(), name=ExplodeCasesView.url_name),
]
