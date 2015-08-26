from collections import defaultdict
from datetime import timedelta
from django.db.models.aggregates import Count
from django.http import HttpResponse
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.generic import GenericTabularReport
from custom.ilsgateway.tanzania.reports.utils import link_format
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import Axis
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter, ViewReportFilter, EWSDateFilter, \
    EWSRestrictionLocationFilter
from custom.ewsghana.reports.stock_levels_report import StockLevelsReport, InventoryManagementData, \
    StockLevelsLegend, FacilityReportData, InputStock, UsersData
from custom.ewsghana.reports import MultiReport, EWSData, EWSMultiBarChart, ProductSelectionPane, EWSLineChart
from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.utils import get_descendants, make_url, get_second_week, get_country_id, get_supply_points


class ProductAvailabilityData(EWSData):
    show_chart = True
    show_table = False
    slug = 'product_availability'

    @property
    def title(self):
        if not self.location:
            return ""

        location_type = self.location.location_type.name.lower()
        if location_type == 'country':
            return "Product availability - National Aggregate"
        elif location_type == 'region':
            return "Product availability - Regional Aggregate"
        elif location_type == 'district':
            return "Product availability - District Aggregate"

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            locations = get_descendants(self.config['location_id'])
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

    @property
    def chart_config(self):
        return {
            'label_color': {
                "Stocked out": "#a30808",
                "Not Stocked out": "#7aaa7a",
                "No Stock Data": "#efde7f"
            },
            'div': "product_availability_summary_plot_placeholder",
            'legenddiv': "product_availability_summary_legend",
            'xaxistitle': "Products",
            'yaxistitle': "Facilities",
        }

    @property
    def charts(self):
        product_availability = self.rows
        if product_availability:
            def convert_product_data_to_stack_chart(rows, chart_config):
                ret_data = []
                for k in ['Stocked out', 'Not Stocked out', 'No Stock Data']:

                    def calculate_percent(x, y):
                        return float(x) / float((y or 1))

                    datalist = []
                    for row in rows:
                        total = row['total']
                        if k == 'No Stock Data':
                            datalist.append([row['product_code'], calculate_percent(row['without_data'], total),
                                             row['product_name']])
                        elif k == 'Stocked out':
                            datalist.append([row['product_code'], calculate_percent(row['without_stock'], total),
                                             row['product_name']])
                        elif k == 'Not Stocked out':
                            datalist.append([row['product_code'], calculate_percent(row['with_stock'], total),
                                             row['product_name']])
                    ret_data.append({'color': chart_config['label_color'][k], 'label': k, 'data': datalist})
                return ret_data
            chart = EWSMultiBarChart('', x_axis=Axis('Products'), y_axis=Axis('', '%'))
            chart.rotateLabels = -45
            chart.marginBottom = 120
            chart.stacked = False
            chart.tooltipFormat = " on "
            chart.forceY = [0, 1]
            chart.product_code_map = {
                sql_product.code: sql_product.name
                for sql_product in SQLProduct.objects.filter(domain=self.domain)
            }
            chart.is_rendered_as_email = self.config.get('is_rendered_as_email', False)
            for row in convert_product_data_to_stack_chart(product_availability, self.chart_config):
                chart.add_dataset(row['label'], [
                    {'x': r[0], 'y': r[1], 'name': r[2]}
                    for r in sorted(row['data'], key=lambda x: x[0])], color=row['color']
                )
            return [chart]
        return []


class MonthOfStockProduct(EWSData):

    slug = 'mos_product'
    show_chart = False
    show_table = True
    use_datatables = True
    default_rows = 25

    @property
    def title(self):
        if not self.location:
            return ""

        if self.config['export']:
            return "Current MOS by Product"

        location_type = self.location.location_type.name.lower()
        if location_type == 'country':
            return "Current MOS by Product - CMS, RMS, and Teaching Hospitals"
        elif location_type == 'region':
            return "Current MOS by Product - RMS and Teaching Hospitals"
        elif location_type == 'district':
            return "Current MOS by Product"

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn('Location'))
        for product in self.unique_products(
            get_supply_points(self.config['domain'], self.config['location_id']), all=(not self.config['export'])
        ):
            if not self.config['export']:
                headers.add_column(DataTablesColumn(product.code))
            else:
                headers.add_column(DataTablesColumn(u'{} ({})'.format(product.name, product.code)))
        return headers

    @property
    def rows(self):
        rows = []
        unique_products = self.unique_products(
            get_supply_points(self.config['domain'], self.config['location_id']), all=(not self.config['export'])
        )
        if self.config['location_id']:
            for case_id, products in self.config['months_of_stock'].iteritems():

                sp = SQLLocation.objects.get(supply_point_id=case_id)

                if sp.location_type.administrative:
                    cls = StockLevelsReport
                else:
                    cls = StockStatus

                url = make_url(
                    cls,
                    self.config['domain'],
                    '?location_id=%s&filter_by_program=%s&startdate=%s&enddate=%s&report_type=%s',
                    (sp.location_id, self.config['program'] or ALL_OPTION, self.config['startdate'].date(),
                    self.config['enddate'].date(), self.config['report_type'])
                )

                row = [
                    link_format(sp.name, url) if not self.config.get('is_rendered_as_email', False) else sp.name
                ]

                for p in unique_products:
                    product_data = products.get(p.product_id)
                    if product_data:
                        value = '%.1f' % product_data
                    else:
                        value = '-'
                    row.append(value)
                rows.append(row)
        return rows


class StockoutsProduct(EWSData):

    slug = 'stockouts_product'
    show_chart = True
    show_table = False
    chart_x_label = 'Months'
    chart_y_label = 'Facility count'
    title = 'Stockout by Product'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        rows = {}
        if self.config['location_id']:
            supply_points = get_descendants(self.config['location_id'])
            products = self.unique_products(supply_points, all=True)
            code_name_map = {}
            for product in products:
                rows[product.code] = []
                code_name_map[product.code] = product.name

            enddate = self.config['enddate']
            startdate = self.config['startdate'] if 'custom_date' in self.config else enddate - timedelta(days=90)
            for d in get_second_week(startdate, enddate):
                txs = list(StockTransaction.objects.filter(
                    case_id__in=list(supply_points.values_list('supply_point_id', flat=True)),
                    sql_product__in=list(products),
                    report__date__range=[d['start_date'], d['end_date']],
                    report__domain=self.config['domain'],
                    type='stockonhand',
                    stock_on_hand=0
                ).values('sql_product__code').annotate(count=Count('case_id')))
                for product in products:
                    if not any([product.code == tx['sql_product__code'] for tx in txs]):
                        rows[product.code].append({'x': d['start_date'], 'y': 0})
                for tx in txs:
                    rows[tx['sql_product__code']].append(
                        {
                            'x': d['start_date'],
                            'y': tx['count'],
                            'name': code_name_map[tx['sql_product__code']]
                        }
                    )
        return rows

    @property
    def charts(self):
        rows = self.rows
        if self.show_chart:
            chart = EWSLineChart("Stockout by Product", x_axis=Axis(self.chart_x_label, dateFormat='%b %Y'),
                                 y_axis=Axis(self.chart_y_label, 'd'))
            chart.x_axis_uses_dates = True
            chart.tooltipFormat = True
            chart.is_rendered_as_email = self.config['is_rendered_as_email']
            for key, value in rows.iteritems():
                chart.add_dataset(key, value)
            return [chart]
        return []


class StockoutTable(EWSData):

    slug = 'stockouts_product_table'
    show_chart = False
    show_table = True

    @property
    def title(self):
        if not self.location:
            return ""
        if self.config['export']:
            return 'Stockouts'

        location_type = self.location.location_type.name.lower()
        if location_type == 'country':
            return "Stockouts - CMS, RMS, and Teaching Hospitals"
        elif location_type == 'region':
            return "Stockouts - RMS and Teaching Hospitals"
        elif location_type == 'district':
            return "Stockouts"

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Location'),
            DataTablesColumn('Stockouts')
        )

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            product_id_to_name = {
                product_id: product_name
                for (product_id, product_name) in self.config['unique_products'].values_list('product_id', 'name')
            }
            for supply_point in self.config['stockout_table_supply_points']:
                products_set = self.config['stockouts'].get(supply_point.supply_point_id)
                url = link_format(supply_point.name, make_url(
                    StockLevelsReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (supply_point.location_id, self.config['startdate'], self.config['enddate'])
                ))
                if products_set:
                    rows.append(
                        [url if not self.config.get('is_rendered_as_email') else supply_point.name, ', '.join(
                            product_id_to_name[product_id] for product_id in products_set
                        )]
                    )
                else:
                    rows.append(
                        [url if not self.config.get('is_rendered_as_email') else supply_point.name, '-']
                    )
        return rows


class StockStatus(MultiReport):
    name = 'Stock status'
    title = 'Stock Status'
    slug = 'stock_status'
    fields = [EWSRestrictionLocationFilter, ProductByProgramFilter, EWSDateFilter, ViewReportFilter]
    split = False
    exportable = True
    is_exportable = True
    is_rendered_as_email = False

    @property
    def fields(self):
        if self.is_reporting_type():
            return [EWSRestrictionLocationFilter, ProductByProgramFilter, ViewReportFilter]
        return [EWSRestrictionLocationFilter, ProductByProgramFilter, EWSDateFilter, ViewReportFilter]

    def unique_products(self, locations):
        return SQLProduct.objects.filter(
            pk__in=locations.values_list('_products', flat=True)
        ).exclude(is_archived=True)

    def get_stock_transactions_for_supply_points_and_products(self, supply_points, unique_products,
                                                              **additional_params):
        return StockTransaction.objects.filter(
            type='stockonhand',
            case_id__in=list(supply_points.values_list('supply_point_id', flat=True)),
            report__domain=self.report_config['domain'],
            report__date__lte=self.report_config['enddate'],
            report__date__gte=self.report_config['startdate'],
            product_id__in=list(unique_products.values_list('product_id', flat=True)),
            **additional_params
        ).distinct('case_id', 'product_id').order_by('case_id', 'product_id', '-report__date').values_list(
            'case_id', 'product_id'
        )

    def get_stockouts_for_supply_points_and_products(self, supply_points, unique_products):
        return self.get_stock_transactions_for_supply_points_and_products(
            supply_points,
            unique_products,
            stock_on_hand=0
        )

    def stockouts_data(self):
        supply_points = get_supply_points(self.report_config['domain'], self.report_config['location_id'])

        if not supply_points:
            return {}

        unique_products = self.unique_products(supply_points)
        transactions = self.get_stockouts_for_supply_points_and_products(
            supply_points, unique_products
        ).values_list('case_id', 'product_id')
        stockouts = defaultdict(set)

        for (case_id, product_id) in transactions:
            stockouts[case_id].add(product_id)

        return {
            'stockouts': stockouts,
            'unique_products': unique_products,
            'stockout_table_supply_points': supply_points
        }

    def data(self):
        locations = self.report_location.get_descendants()
        locations_ids = locations.values_list('supply_point_id', flat=True)

        if not locations_ids:
            return {}

        unique_products = self.unique_products(locations)
        transactions = self.get_stock_transactions_for_supply_points_and_products(
            locations_ids, unique_products
        ).values_list('case_id', 'product_id', 'report__date', 'stock_on_hand')
        current_mos_locations = get_supply_points(self.report_config['domain'], self.report_config['location_id'])
        current_mos_locations_ids = set(
            current_mos_locations.values_list('supply_point_id', flat=True)
        )
        stock_states = StockState.objects.filter(
            sql_product__domain=self.domain,
            case_id__in=current_mos_locations_ids
        )
        product_case_with_stock = defaultdict(set)
        product_case_without_stock = defaultdict(set)

        months_of_stock = defaultdict(lambda: defaultdict(dict))
        stock_state_map = {
            (stock_state.case_id, stock_state.product_id):
            stock_state.get_monthly_consumption() if stock_state.daily_consumption else None
            for stock_state in stock_states
        }

        stockouts = defaultdict(set)
        for (case_id, product_id, date, stock_on_hand) in transactions:
            if stock_on_hand > 0:
                product_case_with_stock[product_id].add(case_id)
                if case_id in current_mos_locations_ids:
                    stock_state_dict = stock_state_map.get((case_id, product_id))
                    if stock_state_dict:
                        months_of_stock[case_id][product_id] = stock_on_hand / stock_state_dict
                    else:
                        months_of_stock[case_id][product_id] = None
            else:
                product_case_without_stock[product_id].add(case_id)
                if case_id in current_mos_locations_ids:
                    stockouts[case_id].add(product_id)
                    months_of_stock[case_id][product_id] = 0

        return {
            'without_stock': {
                product_id: len(case_list)
                for product_id, case_list in product_case_without_stock.iteritems()
            },
            'with_stock': {
                product_id: len(case_list)
                for product_id, case_list in product_case_with_stock.iteritems()
            },
            'all': locations.count(),
            'months_of_stock': months_of_stock,
            'stockouts': stockouts,
            'unique_products': unique_products,
            'stockout_table_supply_points': current_mos_locations
        }

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        products = self.request.GET.getlist('filter_by_product')
        location_id = self.request.GET.get('location_id')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=location_id if location_id else get_country_id(self.domain),
            program=program if program != ALL_OPTION else None,
            products=products if products and products[0] != ALL_OPTION else [],
            report_type=self.request.GET.get('report_type', None),
            user=self.request.couch_user,
            export=False,
            is_rendered_as_email=self.is_rendered_as_email
        )

    @property
    def data_providers(self):
        config = self.report_config
        report_type = self.request.GET.get('report_type', None)

        if self.is_reporting_type():
            self.split = True
            if self.is_rendered_as_email and self.is_rendered_as_print:
                return [
                    FacilityReportData(config),
                    InventoryManagementData(config)
                ]
            elif self.is_rendered_as_email:
                return [
                    FacilityReportData(config)
                ]
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
        if report_type == 'stockouts':
            config.update(self.stockouts_data())
            return [
                ProductSelectionPane(config=config, hide_columns=False),
                StockoutsProduct(config=config),
                StockoutTable(config=config)
            ]
        elif report_type == 'asi':
            config.update(self.data())
            if self.is_rendered_as_email and not self.is_rendered_as_print:
                return [
                    ProductSelectionPane(config=config),
                    MonthOfStockProduct(config=config),
                    StockoutTable(config=config)
                ]

            return [
                ProductSelectionPane(config=config),
                ProductAvailabilityData(config=config),
                MonthOfStockProduct(config=config),
                StockoutsProduct(config=config),
                StockoutTable(config=config)
            ]

        else:
            config.update(self.data())
            providers = [
                ProductSelectionPane(config=config),
                ProductAvailabilityData(config=config),
                MonthOfStockProduct(config=config)
            ]
            if self.is_rendered_as_email and not self.is_rendered_as_print:
                providers.pop(1)
            return providers

    @property
    def export_table(self):
        if self.is_reporting_type():
            return super(StockStatus, self).export_table

        report_type = self.request.GET.get('report_type', None)
        config = self.report_config
        config.update(self.data())
        config['export'] = True
        if report_type == 'stockouts' or not report_type:
            r = MonthOfStockProduct(config=config)
            return [self._export(r.title, r.headers, r.rows)]
        else:
            reports = [
                MonthOfStockProduct(config=config),
                StockoutTable(config=config)
            ]
            return [self._export(r.title, r.headers, r.rows) for r in reports]

    def _export(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        for row in rows:
            row[0] = GenericTabularReport._strip_tags(row[0])
        replace = ''

        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, self._report_info + table]

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.is_rendered_as_print = True
        self.use_datatables = False
        if self.is_reporting_type():
            self.override_template = 'ewsghana/facility_page_print_report.html'
        else:
            self.override_template = "ewsghana/stock_status_print_report.html"
        return HttpResponse(self._async_context()['report'])
