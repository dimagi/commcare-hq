from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.ewsghana.filters import ProductByProgramFilter
from custom.ewsghana.reports import MultiReport, EWSData
from casexml.apps.stock.models import StockTransaction
from dimagi.utils.dates import force_to_datetime


def get_supply_points(location_id, domain):
    loc = SQLLocation.objects.get(location_id=location_id)

    if loc.location_type == 'district':
        locations = SQLLocation.objects.filter(parent=loc)
    elif loc.location_type == 'region':
        locations = SQLLocation.objects.filter(parent__parent=loc)
    else:
        locations = SQLLocation.objects.filter(domain=domain, location_type='facility')
    return locations.exclude(supply_point_id__isnull=True).values_list(*['supply_point_id'], flat=True)


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
        products = SQLProduct.objects.filter(is_archived=False).order_by('code')
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

    @property
    def headers(self):
        headers = DataTablesHeader(*[DataTablesColumn('Location')])

        for product in SQLProduct.objects.filter(is_archived=False, domain=self.config['domain']).order_by('code'):
            headers.add_column(DataTablesColumn(product.code))

        return headers

    @property
    def rows(self):
        products = SQLProduct.objects.filter(is_archived=False, domain=self.config['domain']).order_by('code')
        rows = []
        if self.config['location_id']:
            supply_points = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])\
                .order_by('name').exclude(supply_point_id__isnull=True)
            for sp in supply_points:
                row = [sp.name]
                for p in products:
                    st = StockTransaction.objects.filter(case_id=sp.supply_point_id,
                                                         product_id=p.product_id,
                                                         report__date__range=[
                                                             force_to_datetime(self.config['startdate']),
                                                             force_to_datetime(self.config['enddate'])],
                                                         type='stockonhand',
                                                         report__domain=self.config['domain'])
                    row.append(1)
                rows.append(row)
        return rows


class StockStatus(MultiReport):
    name = 'Stock State'
    title = 'Stock Status'
    slug = 'stock_status'
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter]

    @property
    def report_config(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program=self.request.GET.get('filter_by_program'),
            product=self.request.GET.get('filter_by_product'),
        )

    @property
    def data_providers(self):
        config = self.report_config
        return [ProductAvailabilityData(config=config),
                MonthOfStockProduct(config=config)]