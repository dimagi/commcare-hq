from django.conf.urls import url

from corehq.apps.hqcase.views import (
    ExplodeCasesView,
    case_api,
)

urlpatterns = [
    url(r'^api/$', case_api, name='case_api'),
    url(r'^api/(?P<case_id>[\w-]+)/$', case_api, name='case_api'),

    # for load testing
    url(r'explode/', ExplodeCasesView.as_view(), name=ExplodeCasesView.url_name),
]
