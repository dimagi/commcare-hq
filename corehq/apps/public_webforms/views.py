from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import BaseDomainView, DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.tables.pagination import (
    HtmxInvalidPageRedirectMixin,
    SelectablePaginatedTableView,
)
from corehq.apps.public_webforms.forms import CreatePublicWebformForm
from corehq.apps.public_webforms.models import PublicWebform
from corehq.apps.public_webforms.tables import PublicWebformTable
from corehq.apps.settings.views import get_qrcode
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions


PUBLIC_WEBFORMS_ACCESS = [
    use_bootstrap5,
    require_permission(HqPermissions.edit_public_webforms),
    requires_privilege_with_fallback(privileges.PUBLIC_WEBFORMS),
    toggles.PUBLIC_WEBFORMS.required_decorator(),
]


def public_webforms_access(view):
    """Apply PUBLIC_WEBFORMS_ACCESS to a function view."""
    for decorator in reversed(PUBLIC_WEBFORMS_ACCESS):
        view = decorator(view)
    return view


@method_decorator(PUBLIC_WEBFORMS_ACCESS, name='dispatch')
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


@method_decorator(PUBLIC_WEBFORMS_ACCESS, name='dispatch')
class PublicWebformTableView(
    HtmxInvalidPageRedirectMixin,
    LoginAndDomainMixin,
    DomainViewMixin,
    SelectablePaginatedTableView,
):
    """The dashboard's table of webforms, fetched by the manage view over HTMX."""

    urlname = 'public_webforms_table'
    table_class = PublicWebformTable

    def get_host_url(self):
        # a page that goes out of range is re-rendered against the dashboard
        return reverse(ManagePublicWebformsView.urlname, args=[self.domain])

    def get_queryset(self):
        return PublicWebform.objects.filter(
            domain=self.domain
        ).with_status().annotate(
            submissions=Count(
                'publicformsession',
                filter=Q(publicformsession__submitted_at__isnull=False),
            ),
        ).order_by('-expires_at')

    def get_table_kwargs(self):
        return {
            'domain': self.domain,
            'timezone': self.domain_object.get_default_timezone(),
        }


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


@public_webforms_access
def public_webform_qr_code(request, domain, webform_id):
    """Serve the public URL as a QR code PNG, as ``odk_qr_code`` does for app
    installs, so the dashboard can show one without embedding image data."""
    webform = get_object_or_404(PublicWebform, domain=domain, id=webform_id)
    return HttpResponse(get_qrcode(webform.public_url), content_type='image/png')
