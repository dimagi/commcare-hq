import collections
from collections import OrderedDict
from datetime import timedelta
from itertools import chain
import datetime
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.timesince import timesince
from math import ceil
from casexml.apps.stock.models import StockTransaction
from corehq.apps.es import UserES
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.models import StockState
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import Axis
from corehq.apps.users.models import WebUser
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter, EWSDateFilter, EWSRestrictionLocationFilter
from custom.ewsghana.models import FacilityInCharge, EWSExtension
from custom.ewsghana.reports import EWSData, MultiReport, EWSLineChart, ProductSelectionPane
from custom.ewsghana.utils import has_input_stock_permissions, ews_date_format
from dimagi.utils.couch.database import iter_docs
from memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import get_location, SQLLocation


class InventoryManagementData(EWSData):
    title = ''
    slug = 'inventory_management'
    show_table = False
    show_chart = True
    chart_x_label = 'Weeks'
    chart_y_label = 'MOS'

    @property
    def rows(self):
        return []

    @property
    def chart_data(self):
        def calculate_weeks_remaining(state, daily_consumption, date):
            if not daily_consumption:
                return 0
            consumption = round(float(daily_consumption) * 30.0)
            quantity = float(state.stock_on_hand) - ((date - state.report.date).days // 7) * consumption
            if consumption and consumption > 0 and quantity > 0:
                return quantity / consumption
            return 0

        enddate = self.config['enddate']
        startdate = self.config['startdate'] if 'custom_date' in self.config else enddate - timedelta(days=30)

        loc = SQLLocation.objects.get(location_id=self.config['location_id'])

        stoke_states = StockState.objects.filter(
            case_id=loc.supply_point_id,
            section_id=STOCK_SECTION_TYPE,
            sql_product__in=loc.products,
        )

        consumptions = {ss.product_id: ss.get_daily_consumption() for ss in stoke_states}
        st = StockTransaction.objects.filter(
            case_id=loc.supply_point_id,
            sql_product__in=loc.products,
            type='stockonhand',
            report__date__lte=enddate
        ).select_related('report', 'sql_product').order_by('report__date')

        rows = OrderedDict()
        weeks = ceil((enddate - startdate).days / 7)

        for state in st:
            product_name = '{0} ({1})'.format(state.sql_product.name, state.sql_product.code)
            if product_name not in rows:
                rows[product_name] = {}
            for i in range(1, int(weeks + 1)):
                date = startdate + timedelta(weeks=i)
                if state.report.date < date:
                    rows[product_name][i] = calculate_weeks_remaining(
                        state, consumptions.get(state.product_id, None), date)

        for k, v in rows.items():
            rows[k] = [{'x': key, 'y': value} for key, value in v.items()]

        rows['Understock'] = []
        rows['Overstock'] = []
        for i in range(1, int(weeks + 1)):
            rows['Understock'].append({'x': i, 'y': float(loc.location_type.understock_threshold)})
            rows['Overstock'].append({'x': i, 'y': float(loc.location_type.overstock_threshold)})

        return rows

    @property
    def charts(self):
        if self.show_chart:
            loc = SQLLocation.objects.get(location_id=self.config['location_id'])
            chart = EWSLineChart("Inventory Management Trends", x_axis=Axis(self.chart_x_label, 'd'),
                                 y_axis=Axis(self.chart_y_label, '.1f'))
            chart.height = 600
            values = []
            for product, value in self.chart_data.items():
                values.extend([a['y'] for a in value])
                chart.add_dataset(product, value,
                                  color='black' if product in ['Understock', 'Overstock'] else None)
            chart.forceY = [0, loc.location_type.understock_threshold + loc.location_type.overstock_threshold]
            chart.is_rendered_as_email = self.config.get('is_rendered_as_email', False)
            return [chart]
        return []
