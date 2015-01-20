from datetime import timedelta
from dateutil import rrule
from dateutil.rrule import MO
from corehq import Domain
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis, LineChart
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.ewsghana.filters import ProductByProgramFilter, ViewReportFilter
from custom.ewsghana.reports.stock_levels_report import StockLevelsReport
from custom.ewsghana.reports import MultiReport, EWSData
from casexml.apps.stock.models import StockTransaction
from django.utils import html
from django.db.models import Q


def get_supply_points(location_id, domain):
    loc = SQLLocation.objects.get(location_id=location_id)
    location_types = [loc_type.name for loc_type in filter(
        lambda loc_type: not loc_type.administrative,
        Domain.get_by_name(domain).location_types
    )]
    if loc.location_type == 'district':
        locations = SQLLocation.objects.filter(parent=loc)
    elif loc.location_type == 'region':
        locations = SQLLocation.objects.filter(parent__parent=loc)
    elif loc.location_type in location_types:
        locations = SQLLocation.objects.filter(id=loc.id)
    else:
        locations = SQLLocation.objects.filter(domain=domain, location_type__in=location_types)
    return locations.exclude(supply_point_id__isnull=True).values_list(*['supply_point_id'], flat=True)


def get_second_week(start_date, end_date):
    mondays = list(rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date, byweekday=(MO,), bysetpos=2))
    for monday in mondays:
        yield {
            'start_date': monday,
            'end_date': monday + timedelta(days=6)
        }


def get_products(program_id, products_id, domain):
    if products_id:
        return SQLProduct.objects.filter(product_id__in=products_id)
    elif program_id:
        return SQLProduct.objects.filter(program_id=program_id)
    else:
        return SQLProduct.objects.filter(is_archived=False, domain=domain)


def make_url(report_class, domain, string_params, args):
    try:
        return html.escape(
            report_class.get_url(
                domain=domain
            ) + string_params % args
        )
    except KeyError:
        return None


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
                    datalist = []
                    for row in rows:
                        if k == 'No Stock Data':
                            datalist.append([row['product_code'], row['without_data']])
                        elif k == 'Stocked out':
                            datalist.append([row['product_code'], row['without_stock']])
                        elif k == 'Not Stocked out':
                            datalist.append([row['product_code'], row['with_stock']])
                    ret_data.append({'color': chart_config['label_color'][k], 'label': k, 'data': datalist})
                return ret_data

            chart = MultiBarChart('', x_axis=Axis('Products'), y_axis=Axis(''))
            chart.rotateLabels = -45
            chart.marginBottom = 120
            chart.stacked = False
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
                    (sp.location_id, self.config['program'] or '0', self.config['startdate'],
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
            chart = LineChart("Stockout by Product", x_axis=Axis(self.chart_x_label, dateFormat='%b %Y'),
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
    name = 'Stock State'
    title = 'Stock Status'
    slug = 'stock_status'
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter, ViewReportFilter]
    split = False

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        products = self.request.GET.getlist('filter_by_product')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program=program if program != '0' else None,
            products=products if products and products[0] != '0' else [],
            report_type=self.request.GET.get('report_type', None)
        )

    @property
    def data_providers(self):
        config = self.report_config
        report_type = self.request.GET.get('report_type', None)
        if report_type == 'stockouts':
            return [
                StockoutsProduct(config=config),
                StockoutTable(config=config)
            ]
        elif report_type == 'pa':
            return [
                ProductAvailabilityData(config=config),
                MonthOfStockProduct(config=config)
            ]
        else:
            return [
                ProductAvailabilityData(config=config),
                MonthOfStockProduct(config=config),
                StockoutsProduct(config=config),
                StockoutTable(config=config)
            ]
