from memoized import memoized

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import get_language, gettext_lazy as _

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.public_webforms.models import PublicWebform
from corehq.apps.public_webforms.public.forms import (
    PublicWebformLinkRequestForm,
)


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


@method_decorator(use_bootstrap5, name='dispatch')
class PublicWebformRequestView(BasePublicWebformView):
    urlname = 'public_webform_request'
    template_name = 'public_webforms/public/webform_request.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.webform.is_open:
            return render(
                request,
                'public_webforms/public/webform_closed.html',
                status=404,
            )
        return super().dispatch(request, *args, **kwargs)

    @property
    @memoized
    def form_name(self):
        app = get_app(self.webform.domain, self.webform.app_build_id)
        form = app.get_form(self.webform.form_unique_id) if app else None
        return clean_trans(form.name, [get_language()] + app.langs) if form else None

    @property
    def page_title(self):
        return self.form_name

    def post(self, request, *args, **kwargs):
        if not self.form.is_valid():
            return self.get(request, *args, **kwargs)
        self.form.create_session()
        messages.success(request, _("Your one-time link is on its way."))
        return HttpResponseRedirect(self.page_url)

    @property
    def page_context(self):
        context = super().page_context
        context['form'] = self.form
        return context

    @property
    @memoized
    def form(self):
        data = [self.request.POST] if self.request.method == 'POST' else []
        return PublicWebformLinkRequestForm(self.webform, *data)
