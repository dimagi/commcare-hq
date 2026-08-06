from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.public_webforms.forms import CreatePublicWebformForm
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions


@method_decorator(
    [
        use_bootstrap5,
        require_permission(HqPermissions.edit_public_webforms),
        requires_privilege_with_fallback(privileges.PUBLIC_WEBFORMS),
        toggles.PUBLIC_WEBFORMS.required_decorator(),
    ],
    name='dispatch',
)
class BasePublicWebformsView(BaseDomainView):
    section_name = _("Public Webforms")

    @property
    @memoized
    def section_url(self):
        return reverse(ManagePublicWebformsView.urlname, args=[self.domain])


class ManagePublicWebformsView(BasePublicWebformsView):
    urlname = 'manage_public_webforms'
    template_name = 'public_webforms/manage.html'
    page_title = _("Manage Public Webforms")


class CreatePublicWebformView(BasePublicWebformsView):
    urlname = 'create_public_webform'
    template_name = 'public_webforms/create.html'
    page_title = _("New Public Webform")

    def post(self, request, *args, **kwargs):
        if not self.form.is_valid():
            return self.get(request, *args, **kwargs)
        self.form.create_public_webform()
        messages.success(request, _("Public webform created."))
        return HttpResponseRedirect(
            reverse(ManagePublicWebformsView.urlname, args=[self.domain]))

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'form': self.form,
        })
        return context

    @property
    @memoized
    def form(self):
        data = [self.request.POST] if self.request.method == 'POST' else []
        return CreatePublicWebformForm(
            self.domain, self.domain_object.get_default_timezone(), *data)
