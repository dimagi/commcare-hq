from datetime import timedelta
from django.db.models.aggregates import Count
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.generic import GenericTabularReport
from custom.ilsgateway.tanzania.reports.utils import link_format
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import Axis
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter, ViewReportFilter
from custom.ewsghana.reports.stock_levels_report import StockLevelsReport, InventoryManagementData, \
    FacilityInChargeUsers, FacilityUsers, FacilitySMSUsers, StockLevelsLegend, FacilityReportData, InputStock
from custom.ewsghana.reports import MultiReport, EWSData, EWSMultiBarChart, ProductSelectionPane, EWSLineChart
from casexml.apps.stock.models import StockTransaction
from django.db.models import Q
from custom.ewsghana.utils import get_supply_points, make_url, get_second_week, get_country_id, first_item


class ProductAvailabilityData(EWSData):
    show_chart = True
    show_table = False
    title = 'Product Availability'
    slug = 'product_availability'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            locations = get_supply_points(self.config['location_id'], self.config['domain'])
            supply_points = locations.values_list('supply_point_id', flat=True)
            if not supply_points:
                return rows
            total = supply_points.count()
            for p in self.unique_products(locations, all=True):
                stocks = StockTransaction.objects.filter(
                    type='stockonhand', product_id=p.product_id, case_id__in=supply_points,
                    report__date__lte=self.config['enddate'], report__date__gte=self.config['startdate']
                ).order_by('case_id', '-report__date').distinct('case_id')
                with_stock = stocks.filter(stock_on_hand__gt=0).count()
                without_stock = stocks.filter(stock_on_hand=0).count()
                without_data = total - with_stock - without_stock
                rows.append({"product_code": p.code,
                             "product_name": p.name,
                             "total": total,
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
            chart = EWSMultiBarChart('', x_axis=Axis('Products'), y_axis=Axis('', '.2%'))
            chart.rotateLabels = -45
            chart.marginBottom = 120
            chart.stacked = False
            chart.tooltipFormat = " on "
            chart.forceY = [0, 1]
            for row in convert_product_data_to_stack_chart(product_availability, self.chart_config):
                chart.add_dataset(row['label'], [
                    {'x': r[0], 'y': r[1], 'name': r[2]}
                    for r in sorted(row['data'], key=lambda x: x[0])], color=row['color']
                )
            return [chart]
        return []


class MonthOfStockProduct(EWSData):

    slug = 'mos_product'
    title = 'Current MOS by Product'
    show_chart = False
    show_table = True
    use_datatables = True

    @property
    @memoized
    def get_supply_points(self):
        supply_points = []
        if self.config['location_id']:
            location = SQLLocation.objects.get(
                domain=self.config['domain'],
                location_id=self.config['location_id']
            )
            if location.location_type.name == 'country':
                supply_points = SQLLocation.objects.filter(
                    Q(parent__location_id=self.config['location_id'], is_archived=False) |
                    Q(location_type__name='Regional Medical Store', domain=self.config['domain'])
                ).order_by('name').exclude(supply_point_id__isnull=True)
            else:
                supply_points = SQLLocation.objects.filter(
                    parent__location_id=self.config['location_id'], is_archived=False,
                    location_type__administrative=False,
                ).order_by('name').exclude(supply_point_id__isnull=True)
        return supply_points

    @property
    def headers(self):
        headers = DataTablesHeader(*[DataTablesColumn('Location')])
        for product in self.unique_products(self.get_supply_points, all=True):
            headers.add_column(DataTablesColumn(product.code))

        return headers

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            for sp in self.get_supply_points:
                if sp.location_type.administrative:
                    cls = StockLevelsReport
                else:
                    cls = StockStatus
                url = make_url(
                    cls,
                    self.config['domain'],
                    '?location_id=%s&filter_by_program=%s&startdate=%s&enddate=%s&report_type=%s',
                    (sp.location_id, self.config['program'] or ALL_OPTION, self.config['startdate'].date(),
                    self.config['enddate'].date(), self.config['report_type']))

                row = [link_format(sp.name, url)]
                transactions = list(StockTransaction.objects.filter(
                    type='stockonhand',
                    case_id=sp.supply_point_id,
                    report__date__lte=self.config['enddate']
                ).order_by('-report__date'))

                states = list(StockState.objects.filter(
                    case_id=sp.supply_point_id,
                    section_id='stock'
                ))

                for p in self.unique_products(self.get_supply_points, all=True):
                    transaction = first_item(transactions, lambda x: x.product_id == p.product_id)
                    state = first_item(states, lambda x: x.product_id == p.product_id)

                    if transaction and state:
                        if state.daily_consumption:
                            row.append("%.1f" % (transaction.stock_on_hand / state.get_monthly_consumption()))
                        else:
                            row.append(0)
                    else:
                        row.append('-')
                rows.append(row)
        return rows


class StockoutsProduct(EWSData):

    slug = 'stockouts_product'
    title = 'Stockout by Product'
    show_chart = True
    show_table = False
    chart_x_label = 'Months'
    chart_y_label = 'Facility count'

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        rows = {}
        if self.config['location_id']:
            supply_points = get_supply_points(self.config['location_id'], self.config['domain'])
            products = self.unique_products(supply_points, all=True)
            for product in products:
                rows[product.code] = []

            enddate = self.config['enddate']
            startdate = self.config['startdate'] if 'custom_date' in self.config else enddate - timedelta(days=90)
            for d in get_second_week(startdate, enddate):
                txs = list(StockTransaction.objects.filter(
                    case_id__in=supply_points.values_list('supply_point_id', flat=True),
                    sql_product__in=products,
                    report__date__range=[d['start_date'], d['end_date']],
                    type='stockonhand',
                    stock_on_hand=0
                ).values('sql_product__code').annotate(count=Count('case_id')))
                for tx in txs:
                    rows[tx['sql_product__code']].append({'x': d['start_date'], 'y': tx['count']})
        return rows

    @property
    def charts(self):
        rows = self.rows
        if self.show_chart:
            chart = EWSLineChart("Stockout by Product", x_axis=Axis(self.chart_x_label, dateFormat='%b %Y'),
                                 y_axis=Axis(self.chart_y_label, 'd'))
            chart.x_axis_uses_dates = True
            for key, value in rows.iteritems():
                chart.add_dataset(key, value)
            return [chart]
        return []


class StockoutTable(EWSData):

    slug = 'stockouts_product_table'
    title = 'Stockouts'
    show_chart = False
    show_table = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn('Medical Store'),
            DataTablesColumn('Stockouts')
        ])

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            location = SQLLocation.objects.get(
                domain=self.config['domain'],
                location_id=self.config['location_id']
            )
            if location.location_type.name == 'country':
                supply_points = SQLLocation.objects.filter(
                    Q(parent__location_id=self.config['location_id']) |
                    Q(location_type__name='Regional Medical Store', domain=self.config['domain'])
                ).order_by('name').exclude(supply_point_id__isnull=True).exclude(is_archived=True)
            else:
                supply_points = SQLLocation.objects.filter(
                    parent__location_id=self.config['location_id']
                ).order_by('name').exclude(supply_point_id__isnull=True).exclude(is_archived=True)

            products = set(self.unique_products(supply_points))
            for supply_point in supply_points:
                product_map = {p.product_id: p.name for p in products.intersection(set(supply_point.products))}
                stockout = StockTransaction.objects.filter(
                    type='stockonhand',
                    product_id__in=product_map.keys(),
                    case_id=supply_point.supply_point_id,
                    report__date__lte=self.config['enddate'],
                    report__date__gte=self.config['startdate'],
                    stock_on_hand=0
                ).order_by('product_id', '-report__date').distinct('product_id').values_list('product_id',
                                                                                             flat=True)
                if stockout:
                    rows.append([supply_point.name, ', '.join(product_map[id] for id in stockout)])
        return rows


class StockStatus(MultiReport):
    name = 'Stock status'
    title = 'Stock Status'
    slug = 'stock_status'
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter, ViewReportFilter]
    split = False
    exportable = True
    is_exportable = True

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
            user=self.request.couch_user
        )

    @property
    def data_providers(self):
        config = self.report_config
        report_type = self.request.GET.get('report_type', None)

        if self.is_reporting_type():
            self.split = True
            if self.is_rendered_as_email:
                return [FacilityReportData(config)]
            else:
                return [
                    FacilityReportData(config),
                    StockLevelsLegend(config),
                    InputStock(config),
                    FacilitySMSUsers(config),
                    FacilityUsers(config),
                    FacilityInChargeUsers(config),
                    InventoryManagementData(config),
                    ProductSelectionPane(config)
                ]
        self.split = False
        if report_type == 'stockouts':
            return [
                ProductSelectionPane(config=config),
                StockoutsProduct(config=config),
                StockoutTable(config=config)
            ]
        elif report_type == 'asi':
            return [
                ProductSelectionPane(config=config),
                ProductAvailabilityData(config=config),
                MonthOfStockProduct(config=config),
                StockoutsProduct(config=config),
                StockoutTable(config=config)
            ]
        else:
            return [
                ProductSelectionPane(config=config),
                ProductAvailabilityData(config=config),
                MonthOfStockProduct(config=config)
            ]

    @property
    def export_table(self):
        if self.is_reporting_type():
            return super(StockStatus, self).export_table

        report_type = self.request.GET.get('report_type', None)
        if report_type == 'stockouts' or not report_type:
            r = self.report_context['reports'][2]['report_table']
            return [self._export(r['title'], r['headers'], r['rows'])]
        else:
            reports = [self.report_context['reports'][2]['report_table'],
                       self.report_context['reports'][4]['report_table']]
            return [self._export(r['title'], r['headers'], r['rows']) for r in reports]

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

        return [export_sheet_name, table]
