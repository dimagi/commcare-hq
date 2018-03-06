from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
from django.http import HttpResponse
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.cache import request_cache
from custom.ewsghana.filters import EWSLocationFilter
from custom.ewsghana.reports import MultiReport, ProductSelectionPane
from custom.ewsghana.reports.specific_reports.reporting_rates import ReportingRates, ReportingDetails
from custom.ewsghana.reports.specific_reports.stock_status_report import ProductAvailabilityData
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, InputStock, \
    InventoryManagementData, UsersData
from custom.ewsghana.utils import calculate_last_period
import six


class DashboardReport(MultiReport):

    fields = [EWSLocationFilter]
    name = "Dashboard"
    title = "Dashboard"
    slug = "dashboard_report"
    split = False

    @property
    def report_config(self):
        report_config = super(DashboardReport, self).report_config
        startdate, enddate = calculate_last_period()
        report_config.update(dict(
            startdate=startdate,
            enddate=enddate,
            program=None,
            products=None
        ))
        return report_config

    def data(self):
        complete = 0
        incomplete = 0
        transactions = self.get_stock_transactions().values_list(
            'case_id', 'product_id', 'report__date', 'stock_on_hand'
        )
        grouped_by_case = defaultdict(set)
        all_locations_count = self.location.get_descendants().filter(
            location_type__administrative=False,
            is_archived=False
        ).count()

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

        for case_id, products in six.iteritems(grouped_by_case):
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
                for product_id, case_list in six.iteritems(product_case_without_stock)
            },
            'with_stock': {
                product_id: len(case_list)
                for product_id, case_list in six.iteritems(product_case_with_stock)
            }
        }

    @property
    def data_providers(self):
        config = self.report_config
        if self.is_reporting_type():
            self.emailable = True
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
        self.emailable = False
        config.update(self.data())
        return [
            ProductAvailabilityData(config=config),
            ReportingRates(config=config),
            ReportingDetails(config=config)
        ]

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "ewsghana/dashboard_print_report.html"
        return HttpResponse(self._async_context()['report'])
