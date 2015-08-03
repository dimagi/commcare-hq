from django.contrib.auth.models import User
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.hqcase.dbaccessors import \
    get_supply_point_case_in_domain_by_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.users.models import WebUser
from custom.ewsghana.models import EWSGhanaConfig


class BaseComparisonReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    base_template = 'ilsgateway/base_template.html'
    hide_filters = True
    exportable = True

    @property
    def endpoint(self):
        from custom.ewsghana.api import GhanaEndpoint
        return GhanaEndpoint.from_config(EWSGhanaConfig.for_domain(self.domain))


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
            DataTablesColumn('Date updated'),
            DataTablesColumn('Is active'),
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
                rows.append([location.name, location.type,
                             location.code, location.date_updated, location.is_active, False])

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
            meta, chunk = self.endpoint.get_webusers(offset=offset, limit=1000)
            offset += 1000
            web_users.extend(chunk)

        for web_user in web_users:
            try:
                if not web_user.is_superuser and web_user.groups and web_user.groups[0].name == 'facility_manager':
                    User.objects.get(username="%s@%s.commcarehq.org" % (web_user.username.lower(),
                                                                        self.domain))
                else:
                    user = User.objects.get(username__in=[web_user.username, web_user.email.lower()])
                    webuser = WebUser.get_by_username(user.username)
                    if webuser:
                        if self.domain not in webuser.get_domains():
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
            meta, chunk = self.endpoint.get_smsusers(offset=offset, limit=1000)
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


class SupplyPointsCompareReport(BaseComparisonReport):
    name = "Supply points comparison"
    slug = "supply_points_comparison"

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Name'),
            DataTablesColumn('Type'),
            DataTablesColumn('Code'),
            DataTablesColumn('Is active?'),
            DataTablesColumn('Last reported'),
            DataTablesColumn('Is migrated?')
        )

    @property
    def rows(self):
        rows = []
        supply_points = []
        offset = 1000
        meta, chunk = self.endpoint.get_supply_points(limit=1000)
        supply_points.extend(chunk)
        while meta.get('next', False):
            meta, chunk = self.endpoint.get_supply_points(offset=offset, limit=1000)
            offset += 1000
            supply_points.extend(chunk)

        for supply_point in supply_points:
            couch_sp = get_supply_point_case_in_domain_by_id(
                self.domain, supply_point.id)
            if not couch_sp:
                rows.append([supply_point.name, supply_point.type,
                            supply_point.code, supply_point.active, supply_point.last_reported, False])

        return rows
