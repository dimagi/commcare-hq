from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop
from corehq import Domain
from corehq.apps.commtrack.models import StockState, CommtrackConfig
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.commtrack.data_sources import StockStatusBySupplyPointDataSource
from corehq.apps.reports.commtrack.maps import StockStatusMapReport
from corehq.apps.reports.standard import CustomProjectReport


class EWSStockStatusBySupplyPointDataSource(StockStatusBySupplyPointDataSource):

    def facilities(self, **kwargs):
        reporting_types = [
            loc_type.name for loc_type in Domain.get_by_name(self.config['domain']).location_types
            if not loc_type.administrative
        ]
        return SQLLocation.objects.filter(domain=self.domain, is_archived=False,
                                          location_type__name__in=reporting_types,
                                          **kwargs)

    @property
    def locations(self):
        if not self.active_location:
            return []
        if self.active_location.location_type == 'country':
            return [Location.get(location.location_id) for location in self.facilities()]
        elif self.active_location.location_type == 'region':
            return [Location.get(location.location_id)
                    for location in self.facilities(parent__parent__location_id=self.active_location._id)]
        elif self.active_location.location_type == 'district':
            return [Location.get(location.location_id)
                    for location in self.facilities(parent__location_id=self.active_location._id)]
        else:
            return [self.active_location]

    def _get_icon_and_color(self, value):
        return {
            'stockout': ('remove', 'red'),
            'overstock': ('arrow-up', 'purple'),
            'adequate': ('ok', 'green'),
            'understock': ('warning-sign', 'orange'),
            'no-data': ('', '')
        }[value]

    def get_data(self):
        if self.active_product:
            sql_product = SQLProduct.objects.get(product_id=self.active_product.get_id)
            filtered_locations = [
                location for location in self.locations
                if sql_product in location.sql_location.products
            ]
        else:
            filtered_locations = []
        for loc in filtered_locations:
            case = loc.linked_supply_point()
            if case:
                stock_states = StockState.objects.filter(
                    case_id=loc.linked_supply_point().get_id,
                    section_id=STOCK_SECTION_TYPE,
                    product_id=self.active_product.get_id
                ).order_by('-last_modified_date')
            else:
                stock_states = None
            stock_levels = CommtrackConfig.for_domain(self.domain).stock_levels_config
            category = "no-data"
            if not stock_states:
                quantity = "No data"
                months_until_stockout = None
            else:
                if stock_states[0].get_monthly_consumption():
                    monthly_consumption = int(stock_states[0].get_monthly_consumption())
                else:
                    monthly_consumption = 0
                quantity = stock_states[0].stock_on_hand
                if quantity == 0 or not monthly_consumption:
                    months_until_stockout = 0
                else:
                    months_until_stockout = (stock_states[0].stock_on_hand / monthly_consumption)

                if months_until_stockout is None:
                    category = "no-data"
                if months_until_stockout < stock_levels.understock_threshold:
                    category = 'understock'
                elif stock_levels.understock_threshold < months_until_stockout < stock_levels.overstock_threshold:
                    category = 'adequate'
                elif months_until_stockout == 0:
                    category = 'stockout'
                elif months_until_stockout > stock_levels.overstock_threshold:
                    category = 'overstock'
            icon, color = self._get_icon_and_color(category)
            yield {
                'name': loc.name,
                'type': loc.location_type,
                'geo': loc._geopoint,
                'quantity': quantity,
                'category': category,
                'icon': icon,
                'color': color,
                'months_until_stockout': "%.2f" % months_until_stockout if months_until_stockout is not None
                else "No data",
                'last_reported': stock_states[0].last_modified_date if stock_states else None
            }


class EWSMapReport(CustomProjectReport, StockStatusMapReport):
    name = ugettext_noop("Maps")
    title = ugettext_noop("Maps")
    slug = "ews_mapreport"

    data_source = {
        'adapter': 'report',
        'geo_column': 'geo',
        'report': 'custom.ewsghana.reports.maps.EWSStockStatusBySupplyPointDataSource',
    }

    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'custom.ewsghana.filters.ProductFilter',
    ]

    @property
    def product(self):
        return Product.get(self.request_params['product_id']) if 'product_id' in self.request_params else None

    @property
    def display_config(self):
        conf = {
            'name_column': 'name',
            'detail_template': render_to_string('ewsghana/partials/map_report_table.html', {
                'product': self.product,
                'columns': [
                    {'id': 'quantity', 'title': 'Quantity'},
                    {'id': 'months_until_stockout', 'title': 'Months Until Stockout'},
                    {'id': 'category', 'name': 'Stock status'}
                ],
            }),
            'metrics': [
                {
                    'color': {
                        'column': 'type',
                    },
                },
                {
                    'default': True,
                    'color': {
                        'column': 'category',
                        'categories': {
                            'stockout': 'rgba(255, 0, 0, .8)',
                            'understock': 'rgba(255, 120, 0, .8)',
                            'adequate': 'rgba(50, 200, 50, .8)',
                            'overstock': 'rgba(120, 0, 255, .8)',
                            'no-data': 'rgba(128, 128, 128, .8)',
                        },
                    }
                }
            ],
            'display': {
                'table': False
            }

        }

        return conf
