from django.contrib.auth.models import User
from django.core.urlresolvers import reverse_lazy
from django.shortcuts import get_object_or_404
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.users.models import WebUser
from corehq.util.quickcache import quickcache
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import ILSGatewayConfig, ProductAvailabilityData, SupplyPointStatus


class BaseComparisonReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    base_template = 'ilsgateway/base_template.html'
    hide_filters = True
    exportable = True

    @property
    def endpoint(self):
        return ILSGatewayEndpoint.from_config(ILSGatewayConfig.for_domain(self.domain))

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if user and user.is_domain_admin(domain):
            return True
        return False


class ProductsCompareReport(BaseComparisonReport):
    name = "Products comparison"
    slug = "products_comparison"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn('Name'), DataTablesColumn('Code'), DataTablesColumn('active'),
                                DataTablesColumn('Is migrated'))

    @property
    def rows(self):
        rows = []
        for product in self.endpoint.get_products()[1]:
            try:
                SQLProduct.objects.get(domain=self.domain, code=product.sms_code)
            except SQLProduct.DoesNotExist:
                rows.append([product.name, product.sms_code,
                             product.is_active, False])

        return rows


class LocationsCompareReport(BaseComparisonReport):
    name = "Locations comparison"
    slug = "locations_comparison"

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Name'),
            DataTablesColumn('Type'),
            DataTablesColumn('Code'),
            DataTablesColumn('Is migrated')
        )

    @property
    def rows(self):
        rows = []
        locations = []
        offset = 1000
        meta, chunk = self.endpoint.get_locations(limit=1000)
        locations.extend(chunk)
        while meta.get('next', False):
            meta, chunk = self.endpoint.get_locations(limit=1000, offset=offset)
            offset += 1000
            locations.extend(chunk)

        for location in locations:
            try:
                SQLLocation.objects.get(domain=self.domain, external_id=location.id)
            except SQLLocation.DoesNotExist:
                rows.append([location.name, location.type, location.code, False])
        return rows


class WebUsersCompareReport(BaseComparisonReport):
    name = "Web users comparison"
    slug = "webusers_comparison"

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Username'),
            DataTablesColumn('Email'),
            DataTablesColumn('Date joined'),
            DataTablesColumn('Is active?'),
            DataTablesColumn('Is migrated?')
        )

    @property
    def rows(self):
        rows = []
        web_users = []
        offset = 1000
        meta, chunk = self.endpoint.get_webusers(limit=1000)
        web_users.extend(chunk)
        while meta.get('next', False):
            meta, chunk = self.endpoint.get_webusers(limit=1000, offset=offset)
            offset += 1000
            web_users.extend(chunk)

        for web_user in web_users:
            try:
                user = User.objects.get(username__in=[web_user.username, web_user.email.lower()])
                webuser = WebUser.get_by_username(user.username)
                if webuser and self.domain not in webuser.get_domains():
                    raise User.DoesNotExist
            except User.DoesNotExist:
                rows.append([web_user.username, web_user.email,
                             web_user.date_joined, web_user.is_active, False])
            except User.MultipleObjectsReturned:
                pass

        return rows


class SMSUsersCompareReport(BaseComparisonReport):
    name = "SMS users comparison"
    slug = "smsusers_comparison"

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Username'),
            DataTablesColumn('Email'),
            DataTablesColumn('Date joined'),
            DataTablesColumn('Is active?'),
            DataTablesColumn('Is migrated?')
        )

    @property
    def rows(self):
        rows = []
        sms_users = []
        offset = 1000
        meta, chunk = self.endpoint.get_smsusers(limit=1000)
        sms_users.extend(chunk)
        while meta.get('next', False):
            meta, chunk = self.endpoint.get_smsusers(limit=1000, offset=offset)
            offset += 1000
            sms_users.extend(chunk)

        for sms_user in sms_users:
            domain_part = "%s.commcarehq.org" % self.domain
            username_part = "%s%d" % (sms_user.name.strip().replace(' ', '.').lower(), sms_user.id)
            username = "%s@%s" % (username_part[:(128 - (len(domain_part) + 1))], domain_part)
            try:
                User.objects.get(username=username)
            except User.DoesNotExist:
                rows.append([sms_user.name, sms_user.email,
                             sms_user.date_updated, sms_user.is_active, False])

        return rows


class ProductAvailabilityReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    name = 'Product Availability'
    slug = 'product_availability'
    fields = [AsyncLocationFilter]
    emailable = False
    exportable = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False

    @property
    def location_id(self):
        return self.request.GET.get('location_id', '')

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Date'),
            DataTablesColumn('Product'),
            DataTablesColumn('Total'),
            DataTablesColumn('Without data'),
            DataTablesColumn('With stock'),
            DataTablesColumn('Without stock'),
            DataTablesColumn('')
        )

    @property
    def rows(self):
        data = ProductAvailabilityData.objects.filter(location_id=self.location_id).order_by('date')
        for element in data:
            yield [
                element.date,
                SQLProduct.objects.get(product_id=element.product).name,
                element.total,
                element.without_data,
                element.with_stock,
                element.without_stock,
                '<a href="%s">Delete</a>' % (
                    reverse_lazy('product_availability_delete', kwargs={'domain': self.domain, 'pk': element.pk})
                )
            ]


class SupplyPointStatusReport(GenericTabularReport, DatespanMixin,
                              CustomProjectReport, ProjectReportParametersMixin):
    name = 'Supply Point Status Report'
    slug = 'supply_point_status'
    fields = [AsyncLocationFilter, DatespanFilter]
    emailable = False
    exportable = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False

    @property
    def location_id(self):
        return self.request.GET.get('location_id', '')

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Location'),
            DataTablesColumn('Type'),
            DataTablesColumn('Value'),
            DataTablesColumn('Date'),
        )

    @quickcache(['location_id'], timeout=30 * 60)
    def _get_location_name(self, location_id):
        return SQLLocation.objects.get(location_id=location_id).name

    @property
    def rows(self):
        locations = get_object_or_404(
            SQLLocation, location_id=self.location_id
        ).get_descendants(include_self=True)
        data = SupplyPointStatus.objects.filter(
            location_id__in=list(locations.values_list('location_id', flat=True)),
            status_date__range=[self.datespan.startdate, self.datespan.enddate]
        ).order_by('-status_date')
        for element in data:
            yield [
                self._get_location_name(element.location_id),
                element.status_type,
                element.status_value,
                element.status_date
            ]
