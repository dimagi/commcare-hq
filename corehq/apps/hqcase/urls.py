from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.hqcase.views import ExplodeCasesView

urlpatterns = [
    # for load testing
    url(r'explode/', ExplodeCasesView.as_view(), name=ExplodeCasesView.url_name)
]
