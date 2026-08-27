from memoized import memoized

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.public_webforms.models import PublicWebform


class BasePublicWebformView(BasePageView):

    @property
    @memoized
    def webform(self):
        return get_object_or_404(PublicWebform, public_id=self.kwargs.get('public_id'))

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs={'public_id': self.webform.public_id.hex})

    @property
    def main_context(self):
        context = super().main_context
        context['section'] = {'page_name': _("One-Time Link Request")}
        return context
