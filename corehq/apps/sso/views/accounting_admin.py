from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.filters import (
    DateCreatedFilter,
    NameFilter,
)
from corehq.apps.accounting.interface import AddItemInterface
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.toggles import ENTERPRISE_SSO

from corehq.apps.sso.models import IdentityProvider


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
    ]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return ENTERPRISE_SSO.enabled(user.username)

    @property
    def new_item_view(self):
        # todo replace with NewIdentityProviderView
        #return NewIdentityProviderAdminView
        return ""

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name"),
            DataTablesColumn("Slug"),
            DataTablesColumn("Edit Status"),
            DataTablesColumn("Active Status"),
            DataTablesColumn("Account Owner Name"),
        )

    @property
    def rows(self):
        def _idp_to_row(idp):
            edit_url = ''
            #edit_url = reverse(EditIdentityProviderAdminView.urlname, args=(idp.id,))
            return [
                f'<a href="{edit_url}">{idp.name}</a>',
                idp.slug,
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

        return queryset
