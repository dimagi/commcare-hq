from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop
from corehq.apps.commtrack.models import StockState, CommtrackConfig
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.commtrack.data_sources import StockStatusBySupplyPointDataSource
from corehq.apps.reports.commtrack.maps import StockStatusMapReport
from corehq.apps.reports.standard import CustomProjectReport
from custom.ewsghana.utils import get_country_id, filter_slugs_by_role
from dimagi.utils.decorators.memoized import memoized


class EWSStockStatusBySupplyPointDataSource(StockStatusBySupplyPointDataSource):

    def facilities(self, **kwargs):
        return SQLLocation.objects.filter(domain=self.domain, is_archived=False,
                                          location_type__administrative=False,
                                          **kwargs)

    @property
    @memoized
    def active_location(self):
        return SQLLocation.objects.get(domain=self.domain, location_id=self.config.get('location_id'))

    @property
    def locations(self):
        locations = self.active_location.get_descendants(
            include_self=True
        ).filter(location_type__administrative=False).exclude(is_archived=True)
        if 'loc_type' in self.config and self.config['loc_type']:
            if isinstance(self.config['loc_type'], basestring):
                self.config['loc_type'] = [self.config['loc_type']]
            locations = locations.filter(location_type__pk__in=self.config['loc_type'])
        return locations

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
                if sql_product in location.products
            ]
        else:
            filtered_locations = []
        for location in filtered_locations:
            if location.supply_point_id:
                stock_states = StockState.objects.filter(
                    case_id=location.supply_point_id,
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
                monthly_consumption = None
                if stock_states[0].daily_consumption:
                    monthly_consumption = stock_states[0].daily_consumption * 30
                quantity = stock_states[0].stock_on_hand
                if not monthly_consumption:
                    months_until_stockout = None
                else:
                    months_until_stockout = (float(stock_states[0].stock_on_hand) / float(monthly_consumption))

                if quantity == 0:
                    category = 'stockout'
                    months_until_stockout = 0
                elif months_until_stockout is None:
                    category = "no-data"
                elif months_until_stockout < location.location_type.understock_threshold:
                    category = 'understock'
                elif stock_levels.understock_threshold < months_until_stockout < \
                        location.location_type.overstock_threshold:
                    category = 'adequate'
                elif months_until_stockout > location.location_type.overstock_threshold:
                    category = 'overstock'
            icon, color = self._get_icon_and_color(category)
            geo_point = None
            if location.latitude is not None and location.latitude is not None:
                geo_point = '%s %s' % (location.latitude, location.longitude)
            yield {
                'name': location.name,
                'type': location.location_type.name,
                'geo': geo_point,
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
    template_report = 'ewsghana/map_template.html'
    report_partial_path = "ewsghana/partials/map.html"

    data_source = {
        'adapter': 'report',
        'geo_column': 'geo',
        'report': 'custom.ewsghana.reports.maps.EWSStockStatusBySupplyPointDataSource',
    }

    fields = [
        'custom.ewsghana.filters.EWSRestrictionLocationFilter',
        'custom.ewsghana.filters.ProductFilter',
        'custom.ewsghana.filters.LocationTypeFilter'
    ]

    def _get_data(self):
        adapter = self.data_source['adapter']
        geo_col = self.data_source.get('geo_column', 'geo')

        try:
            loader = getattr(self, '_get_data_%s' % adapter)
        except AttributeError:
            raise RuntimeError('unknown adapter [%s]' % adapter)
        config = dict(self.request.GET.iterlists())
        for k, v in config.iteritems():
            if len(v) == 1:
                config[k] = v[0]
        data = loader(self.data_source, config)

        return self._to_geojson(data, geo_col)

    @property
    def report_context(self):
        context = super(StockStatusMapReport, self).report_context
        context['context']['slugs'] = filter_slugs_by_role(self.request.couch_user, self.domain)
        return context

    @classmethod
    def get_url(cls, domain=None, render_as=None, **kwargs):
        url = super(EWSMapReport, cls).get_url(domain=domain, render_as=None, kwargs=kwargs)
        request = kwargs.get('request')
        user = getattr(request, 'couch_user', None)

        if user:
            product = SQLProduct.objects.filter(domain=domain, is_archived=False).\
                values_list('product_id', flat=True).order_by('name')

            url = '%s?location_id=%s&product_id=%s' % (
                url,
                user.location_id if user.location_id else get_country_id(domain),
                product[0] if product else ''
            )
        return url

    @property
    def product(self):
        return Product.get(self.request_params['product_id']) if 'product_id' in self.request_params else None

    @property
    def display_config(self):
        categories = {
            'Central Medical Store': 'rgba(80, 0, 0, .8)',
            'Teaching Hospital': 'rgba(80, 120, 0, .8)',
            'Regional Medical Store': 'rgba(80, 240, 0, .8)',
            'Regional Hospital': 'rgba(150, 0, 0, .8)',
            'Clinic': 'rgba(150, 120, 0, .8)',
            'District Hospital': 'rgba(190, 240, 255, .8)',
            'CHPS Facility': 'rgba(220, 120, 150, .8)',
            'Hospital': 'rgba(220, 120, 0, .8)',
            'Psychiatric Hospital': 'rgba(220, 180, 50, .8)',
            'Polyclinic': 'rgba(200, 255, 0, .8)',
            'Health Centre': 'rgba(255, 0, 255, .8)'
        }

        conf = {
            'name_column': 'name',
            'detail_template': render_to_string('ewsghana/partials/map_report_table.html', {
                'product': self.product,
                'columns': [
                    {'id': 'quantity', 'title': 'Quantity'},
                    {'id': 'months_until_stockout', 'title': 'Months of Stock'},
                    {'id': 'category', 'name': 'Stock status'}
                ],
            }),
            'metrics': [
                {
                    'color': {
                        'column': 'type',
                        'categories': categories
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
