from django.conf.urls import url

from corehq.apps.hqcase.views import (
    ExplodeCasesView,
    case_api,
)

urlpatterns = [
    # for load testing
    url(r'explode/', ExplodeCasesView.as_view(), name=ExplodeCasesView.url_name),
]

case_api_urlpatterns = [
    url(r'^$', case_api, name='case_api'),
    url(r'^(?P<case_id>[\w-]+)/?$', case_api, name='case_api'),
]
