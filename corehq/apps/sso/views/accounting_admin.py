from memoized import memoized

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy
from django.utils.html import format_html

from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.filters import (
    DateCreatedFilter,
    NameFilter,
    IdPServiceTypeFilter,
)
from corehq.apps.accounting.interface import AddItemInterface
from corehq.apps.accounting.views import AccountingSectionView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.sso.certificates import get_certificate_response

from corehq.apps.sso.forms import (
    CreateIdentityProviderForm,
    EditIdentityProviderAdminForm,
)
from corehq.apps.sso.async_handlers import (
    Select2IdentityProviderHandler,
    IdentityProviderAdminAsyncHandler,
    SSOExemptUsersAdminAsyncHandler,
    SsoTestUserAdminAsyncHandler,
)
from corehq.apps.sso.models import (
    IdentityProvider,
    IdentityProviderProtocol,
    AuthenticatedEmailDomain,
    TrustedIdentityProvider,
)


class IdentityProviderInterface(AddItemInterface):
    section_name = 'Accounting'
    name = 'Identity Providers (SSO)'
    description = 'For managing identity providers for Single Sign On (SSO)'
    slug = 'identity_providers'
    dispatcher = AccountingAdminInterfaceDispatcher
    hide_filters = False
    item_name = "Identity Provider"

    fields = [
        'corehq.apps.accounting.interface.DateCreatedFilter',
        'corehq.apps.accounting.interface.NameFilter',
        'corehq.apps.accounting.filters.IdPServiceTypeFilter',
    ]

    @property
    def new_item_view(self):
        return NewIdentityProviderAdminView

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name"),
            DataTablesColumn("Slug"),
            DataTablesColumn("Service"),
            DataTablesColumn("Edit Status"),
            DataTablesColumn("Active Status"),
            DataTablesColumn("Account Owner Name"),
        )

    @property
    def rows(self):
        def _idp_to_row(idp):
            edit_url = reverse(EditIdentityProviderAdminView.urlname, args=(idp.id,))
            return [
                format_html('<a href="{}">{}</a>', edit_url, idp.name),
                idp.slug,
                idp.service_name,
                "Open" if idp.is_editable else "Closed",
                "Active" if idp.is_active else "Inactive",
                idp.owner.name,
            ]

        return list(map(_idp_to_row, self._identity_providers))

    @property
    def _identity_providers(self):
        queryset = IdentityProvider.objects.all()

        if DateCreatedFilter.use_filter(self.request):
            queryset = queryset.filter(
                date_created__gte=DateCreatedFilter.get_start_date(
                    self.request),
                date_created__lte=DateCreatedFilter.get_end_date(self.request),
            )
        name = NameFilter.get_value(self.request, self.domain)
        if name is not None:
            queryset = queryset.filter(
                owner__name=name,
            )
        idp_type = IdPServiceTypeFilter.get_value(
            self.request, self.domain
        )
        if idp_type is not None:
            queryset = queryset.filter(
                idp_type=idp_type,
            )

        return queryset


class BaseIdentityProviderAdminView(AccountingSectionView):
    @property
    def parent_pages(self):
        return [{
            'title': IdentityProviderInterface.name,
            'url': IdentityProviderInterface.get_url(),
        }]


class NewIdentityProviderAdminView(BaseIdentityProviderAdminView, AsyncHandlerMixin):
    page_title = 'New Identity Provider'
    template_name = 'sso/accounting_admin/new_identity_provider.html'
    urlname = 'new_identity_provider'
    async_handlers = [
        Select2IdentityProviderHandler,
    ]

    @property
    @memoized
    def create_idp_form(self):
        if self.request.method == 'POST':
            return CreateIdentityProviderForm(self.request.POST)
        return CreateIdentityProviderForm()

    @property
    def page_context(self):
        return {
            'create_idp_form': self.create_idp_form,
            'idp_types_by_protocol': IdentityProviderProtocol.get_supported_types(),
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.create_idp_form.is_valid():
            idp = self.create_idp_form.create_identity_provider(self.request.user)
            messages.success(request, "New Identity Provider created!")
            return HttpResponseRedirect(
                reverse(EditIdentityProviderAdminView.urlname, args=(idp.id,))
            )
        return self.get(request, *args, **kwargs)


class EditIdentityProviderAdminView(BaseIdentityProviderAdminView, AsyncHandlerMixin):
    page_title = gettext_lazy('Edit Identity Provider')
    template_name = 'sso/accounting_admin/edit_identity_provider.html'
    urlname = 'edit_identity_provider'
    async_handlers = [
        IdentityProviderAdminAsyncHandler,
        SSOExemptUsersAdminAsyncHandler,
        SsoTestUserAdminAsyncHandler,
    ]

    @property
    @memoized
    def is_deletion_request(self):
        return self.request.POST.get('delete_identity_provider')

    @property
    @memoized
    def edit_idp_form(self):
        if self.request.method == 'POST' and not self.is_deletion_request:
            return EditIdentityProviderAdminForm(self.identity_provider, self.request.POST)
        return EditIdentityProviderAdminForm(self.identity_provider)

    @property
    def page_context(self):
        return {
            'edit_idp_form': self.edit_idp_form,
            'idp_slug': self.identity_provider.slug,
            'idp_is_active': self.identity_provider.is_active,
        }

    @property
    @memoized
    def identity_provider(self):
        try:
            return IdentityProvider.objects.get(id=self.args[0])
        except ObjectDoesNotExist:
            raise Http404()

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.identity_provider.id,))

    def get(self, request, *args, **kwargs):
        if 'sp_cert_public' in request.GET:
            return get_certificate_response(
                self.identity_provider.sp_cert_public,
                f"{self.identity_provider.slug}_sp_public.cer"
            )
        if 'sp_rollover_cert_public' in request.GET:
            return get_certificate_response(
                self.identity_provider.sp_rollover_cert_public,
                f"{self.identity_provider.slug}_sp_rollover_public.cer"
            )
        return super().get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.is_deletion_request and self.identity_provider.is_active:
            messages.error(
                request,
                _("Identity Provider {} cannot be deleted because "
                  "it is still active.").format(
                    self.identity_provider.name
                )
            )
        elif self.is_deletion_request:
            AuthenticatedEmailDomain.objects.filter(identity_provider=self.identity_provider).delete()
            TrustedIdentityProvider.objects.filter(identity_provider=self.identity_provider).delete()
            self.identity_provider.delete()
            messages.success(
                request,
                _("Identity Provider {} successfully deleted.").format(
                    self.identity_provider.name
                )
            )
            return HttpResponseRedirect(IdentityProviderInterface.get_url())
        elif self.edit_idp_form.is_valid():
            self.edit_idp_form.update_identity_provider(self.request.user)
            messages.success(request, _("Identity Provider updated!"))
            # we redirect here to force the memoized identity_provider property
            # to re-fetch its data.
            return HttpResponseRedirect(self.page_url)
        return self.get(request, *args, **kwargs)
