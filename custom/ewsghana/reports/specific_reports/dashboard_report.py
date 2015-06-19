from collections import defaultdict
from datetime import datetime
from corehq.apps.locations.models import SQLLocation
from custom.ewsghana.filters import EWSLocationFilter
from custom.ewsghana.reports import MultiReport, ProductSelectionPane
from custom.ewsghana.reports.specific_reports.reporting_rates import ReportingRates, ReportingDetails
from custom.ewsghana.reports.specific_reports.stock_status_report import ProductAvailabilityData
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, InputStock, \
    InventoryManagementData, UsersData
from custom.ewsghana.utils import get_country_id, calculate_last_period, get_supply_points


class DashboardReportProductAvailability(ProductAvailabilityData):

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            locations = get_supply_points(self.config['location_id'], self.config['domain'])
            unique_products = self.unique_products(locations, all=True).order_by('code')

            for product in unique_products:
                with_stock = self.config['with_stock'].get(product.product_id, 0)
                without_stock = self.config['without_stock'].get(product.product_id, 0)
                without_data = self.config['all'] - with_stock - without_stock
                rows.append({"product_code": product.code,
                             "product_name": product.name,
                             "total": self.config['all'],
                             "with_stock": with_stock,
                             "without_stock": without_stock,
                             "without_data": without_data})
        return rows


class DashboardReport(MultiReport):

    fields = [EWSLocationFilter]
    name = "Dashboard"
    title = "Dashboard"
    slug = "dashboard_report"
    split = False

    @property
    def report_config(self):
        startdate, enddate = calculate_last_period(datetime.utcnow())
        return dict(
            domain=self.domain,
            startdate=startdate,
            enddate=enddate,
            location_id=self.request.GET.get('location_id') or get_country_id(self.domain),
            user=self.request.couch_user,
            program=None,
            products=None
        )

    def data(self):
        complete = 0
        incomplete = 0
        transactions = self.get_stock_transactions().values_list(
            'case_id', 'product_id', 'report__date', 'stock_on_hand'
        )
        grouped_by_case = defaultdict(set)
        all_locations_count = SQLLocation.objects.get(
            location_id=self.report_config['location_id']
        ).get_descendants().count()

        product_case_with_stock = defaultdict(set)
        product_case_without_stock = defaultdict(set)

        for (case_id, product_id, date, stock_on_hand) in transactions:
            if stock_on_hand > 0:
                product_case_with_stock[product_id].add(case_id)
                if case_id in product_case_without_stock[product_id]:
                    product_case_without_stock[product_id].remove(case_id)
            else:
                product_case_without_stock[product_id].add(case_id)
                if case_id in product_case_with_stock[product_id]:
                    product_case_with_stock[product_id].remove(case_id)
            grouped_by_case[case_id].add(product_id)

        for case_id, products in grouped_by_case.iteritems():
            location = SQLLocation.objects.get(
                supply_point_id=case_id
            )
            if not (set(location.products.values_list('product_id', flat=True)) - products):
                complete += 1
            else:
                incomplete += 1

        return {
            'all': all_locations_count,
            'complete': complete,
            'incomplete': incomplete,
            'non_reporting': all_locations_count - (complete + incomplete),
            'without_stock': {
                product_id: len(case_list)
                for product_id, case_list in product_case_without_stock.iteritems()
            },
            'with_stock': {
                product_id: len(case_list)
                for product_id, case_list in product_case_with_stock.iteritems()
            }
        }

    @property
    def data_providers(self):
        config = self.report_config
        if self.is_reporting_type():
            self.split = True
            if self.is_rendered_as_email:
                return [FacilityReportData(config)]
            else:
                return [
                    FacilityReportData(config),
                    StockLevelsLegend(config),
                    InputStock(config),
                    UsersData(config),
                    InventoryManagementData(config),
                    ProductSelectionPane(config, hide_columns=False)
                ]
        self.split = False
        config.update(self.data())
        return [
            DashboardReportProductAvailability(config=config),
            ReportingRates(config=config),
            ReportingDetails(config=config)
        ]
