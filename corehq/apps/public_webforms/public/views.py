from memoized import memoized

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.public_webforms.models import PublicWebform


@method_decorator(use_bootstrap5, name='dispatch')
class PublicWebformRequestView(BasePageView):
    urlname = 'public_webform_request'

    @property
    @memoized
    def webform(self):
        return get_object_or_404(PublicWebform, public_id=self.kwargs.get('public_id'))

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs={'public_id': self.webform.public_id.hex})
