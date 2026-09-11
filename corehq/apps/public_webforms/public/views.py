from memoized import memoized

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.timesince import timeuntil
from django.utils.translation import get_language, gettext_lazy as _

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.public_webforms.messaging import send_one_time_link
from corehq.apps.public_webforms.models import PublicFormSession, PublicWebform
from corehq.apps.public_webforms.public.forms import (
    PublicWebformLinkRequestForm,
)


def public_webforms_enabled(domain):
    return (
        domain_has_privilege(domain, privileges.PUBLIC_WEBFORMS)
        and toggles.PUBLIC_WEBFORMS.enabled(domain, namespace=toggles.NAMESPACE_DOMAIN)
    )


class BasePublicWebformView(BasePageView):

    @property
    @memoized
    def webform(self):
        webform = get_object_or_404(
            PublicWebform, public_id=self.kwargs.get('public_id'))
        if not public_webforms_enabled(webform.domain):
            raise Http404
        return webform

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
        send_one_time_link(self.form.get_or_create_session(), self.form_name)
        return HttpResponseRedirect(reverse(
            PublicWebformLinkSentView.urlname,
            kwargs={'public_id': self.webform.public_id.hex},
        ))

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


@method_decorator(use_bootstrap5, name='dispatch')
class PublicWebformLinkSentView(BasePublicWebformView):

    urlname = 'public_webform_link_sent'
    template_name = 'public_webforms/public/webform_link_sent.html'

    @property
    def page_context(self):
        context = super().page_context
        now = timezone.now()
        context.update({
            # the session is not carried across the redirect, so this is how
            # long any link lasts, not how long this respondent's link has left
            'link_lifespan': timeuntil(
                now + PublicFormSession.DEFAULT_LIFESPAN, now),
            'request_url': reverse(
                PublicWebformRequestView.urlname,
                kwargs={'public_id': self.webform.public_id.hex},
            ) if self.webform.is_open else None,
        })
        return context
