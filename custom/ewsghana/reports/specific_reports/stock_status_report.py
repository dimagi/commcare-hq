from corehq import Domain
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import Axis
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter, ViewReportFilter
from custom.ewsghana.reports.stock_levels_report import StockLevelsReport, InventoryManagementData, \
    FacilityInChargeUsers, FacilityUsers, FacilitySMSUsers, StockLevelsLegend, FacilityReportData
from custom.ewsghana.reports import MultiReport, EWSData, EWSMultiBarChart, ProductSelectionPane, EWSLineChart
from casexml.apps.stock.models import StockTransaction
from django.db.models import Q
from custom.ewsghana.utils import get_supply_points, get_products, make_url, get_second_week


def link_format(text, url):
    return '<a href=%s>%s</a>' % (url, text)


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
        products = get_products(self.config['program'],
                                self.config['products'],
                                self.config['domain']).order_by('code')
        rows = []
        if self.config['location_id']:
            for p in products:
                supply_points = get_supply_points(self.config['location_id'], self.config['domain'])
                if supply_points:
                    stocks = StockState.objects.filter(sql_product=p, case_id__in=supply_points)
                    total = supply_points.count()
                    with_stock = stocks.filter(stock_on_hand__gt=0).count()
                    without_stock = stocks.filter(stock_on_hand=0).count()
                    without_data = total - with_stock - without_stock
                    rows.append({"product_code": p.code,
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
                            datalist.append([row['product_code'], calculate_percent(row['without_data'], total)])
                        elif k == 'Stocked out':
                            datalist.append([row['product_code'], calculate_percent(row['without_stock'], total)])
                        elif k == 'Not Stocked out':
                            datalist.append([row['product_code'], calculate_percent(row['with_stock'], total)])
                    ret_data.append({'color': chart_config['label_color'][k], 'label': k, 'data': datalist})
                return ret_data
            chart = EWSMultiBarChart('', x_axis=Axis('Products'), y_axis=Axis('', '.2%'))
            chart.rotateLabels = -45
            chart.marginBottom = 120
            chart.stacked = False
            chart.forceY = [0, 1]
            for row in convert_product_data_to_stack_chart(product_availability, self.chart_config):
                chart.add_dataset(row['label'], [
                    {'x': r[0], 'y': r[1]}
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
    def headers(self):
        headers = DataTablesHeader(*[DataTablesColumn('Location')])

        for product in get_products(self.config['program'],
                                    self.config['products'],
                                    self.config['domain']).order_by('code'):
            headers.add_column(DataTablesColumn(product.code))

        return headers

    @property
    def rows(self):
        products = get_products(self.config['program'],
                                self.config['products'],
                                self.config['domain']).order_by('code')
        rows = []
        if self.config['location_id']:
            location = SQLLocation.objects.get(
                domain=self.config['domain'],
                location_id=self.config['location_id']
            )
            if location.location_type == 'country':
                supply_points = SQLLocation.objects.filter(
                    Q(parent__location_id=self.config['location_id']) |
                    Q(location_type='Regional Medical Store', domain=self.config['domain'])
                ).order_by('name').exclude(supply_point_id__isnull=True)
            else:
                supply_points = SQLLocation.objects.filter(
                    parent__location_id=self.config['location_id']
                ).order_by('name').exclude(supply_point_id__isnull=True)

            for sp in supply_points:
                location_types = [loc_type.name for loc_type in filter(
                    lambda loc_type: not loc_type.administrative,
                    Domain.get_by_name(self.config['domain']).location_types
                )]
                if sp.location_type in location_types:
                    cls = StockLevelsReport
                else:
                    cls = StockStatus
                url = make_url(
                    cls,
                    self.config['domain'],
                    '?location_id=%s&filter_by_program=%s&startdate=%s'
                    '&enddate=%s&report_type=%s&filter_by_product=%s',
                    (sp.location_id, self.config['program'] or ALL_OPTION, self.config['startdate'],
                    self.config['enddate'], self.config['report_type'],
                    '&filter_by_product='.join(self.config['products'])))

                row = [link_format(sp.name, url)]
                for p in products:
                    stock = StockState.objects.filter(sql_product=p, case_id=sp.supply_point_id)\
                        .order_by('-last_modified_date')

                    if stock:
                        monthly = stock[0].get_monthly_consumption()
                        if monthly:
                            row.append(int(stock[0].stock_on_hand / monthly))
                        else:
                            row.append('-')
                    else:
                        row.append(0)
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
            products = get_products(self.config['program'],
                                    self.config['products'],
                                    self.config['domain']).order_by('code')

            for product in products:
                rows[product.code] = []

            for d in get_second_week(self.config['startdate'], self.config['enddate']):
                for product in products:
                    st = StockTransaction.objects.filter(case_id__in=supply_points,
                                                         sql_product=product,
                                                         report__date__range=[d['start_date'],
                                                                              d['end_date']],
                                                         type='stockonhand',
                                                         stock_on_hand=0).count()

                    rows[product.code].append({'x': d['start_date'], 'y': st})
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
    use_datatables = True

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
            if location.location_type == 'country':
                supply_points = SQLLocation.objects.filter(
                    Q(parent__location_id=self.config['location_id']) |
                    Q(location_type='Regional Medical Store', domain=self.config['domain'])
                ).order_by('name').exclude(supply_point_id__isnull=True)
            else:
                supply_points = SQLLocation.objects.filter(
                    parent__location_id=self.config['location_id']
                ).order_by('name').exclude(supply_point_id__isnull=True)
            products = SQLProduct.objects.filter(is_archived=False, domain=self.config['domain'])

            for supply_point in supply_points:
                stockout = StockState.objects.filter(sql_product__in=products,
                                                     case_id=supply_point.supply_point_id,
                                                     stock_on_hand=0).values_list(*['sql_product__name'],
                                                                                  flat=True)
                if stockout:
                    rows.append([supply_point.name, ', '.join(stockout)])
        return rows


class StockStatus(MultiReport):
    name = 'Stock status'
    title = 'Stock Status'
    slug = 'stock_status'
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter, ViewReportFilter]
    split = False
    exportable = True

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        products = self.request.GET.getlist('filter_by_product')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program=program if program != ALL_OPTION else None,
            products=products if products and products[0] != ALL_OPTION else [],
            report_type=self.request.GET.get('report_type', None)
        )

    @property
    def export_table(self):
        if not self.is_reporting_type():
            return super(StockStatus, self).export_table
        r = self.report_context['reports'][0]['report_table']
        return [self._export_table(r['title'], r['headers'], r['rows'])]

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
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

    @property
    def data_providers(self):
        config = self.report_config
        report_type = self.request.GET.get('report_type', None)

        if self.is_reporting_type():
            self.split = True
            return [
                FacilityReportData(config),
                StockLevelsLegend(config),
                FacilitySMSUsers(config),
                FacilityUsers(config),
                FacilityInChargeUsers(config),
                InventoryManagementData(config)
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

