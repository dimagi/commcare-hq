from collections import defaultdict
from datetime import timedelta
from django.db.models.aggregates import Count
from django.http import HttpResponse
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.generic import GenericTabularReport
from custom.ewsghana.reports.utils import link_format
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import Axis
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter, ViewReportFilter, EWSDateFilter, \
    EWSRestrictionLocationFilter
from custom.ewsghana.reports.stock_levels_report import InventoryManagementData, \
    StockLevelsLegend, FacilityReportData, InputStock, UsersData
from custom.ewsghana.reports import MultiReport, EWSData, EWSMultiBarChart, ProductSelectionPane, EWSLineChart
from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.utils import get_descendants, make_url, get_second_week, get_supply_points


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
                headers.add_column(DataTablesColumn('{} ({})'.format(product.name, product.code)))
        return headers

    @property
    def rows(self):
        rows = []
        unique_products = self.unique_products(
            get_supply_points(self.config['domain'], self.config['location_id']), all=(not self.config['export'])
        )
        if self.config['location_id']:
            for case_id, products in self.config['months_of_stock'].items():

                sp = SQLLocation.objects.get(supply_point_id=case_id)

                url = make_url(
                    StockStatus,
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
            chart.is_rendered_as_email = self.config.get('is_rendered_as_email')
            for key, value in rows.items():
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
                    StockStatus,
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
