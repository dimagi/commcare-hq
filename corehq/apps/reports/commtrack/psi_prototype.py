from django.conf import settings
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.locations.models import Location, root_locations, all_locations
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils import parsing as dateparse
import itertools
from datetime import date, timedelta
from corehq.apps.commtrack.models import CommtrackConfig, Product, StockReport
from corehq.apps.commtrack.util import *
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.cache import request_cache
import json
from casexml.apps.case.models import CommCareCase

class CommtrackReportMixin(ProjectReport, ProjectReportParametersMixin):

    @classmethod
    def show_in_navigation(cls, request, domain=None):
        try:
            return request.project.commtrack_enabled
        except Exception:
            if settings.DEBUG:
                raise
            else:
                domain = Domain.get_by_name(domain)
                return domain.commtrack_enabled

    @property
    def config(self):
        return CommtrackConfig.for_domain(self.domain)

    @property
    @memoized
    def products(self):
        prods = Product.by_domain(self.domain, wrap=False)
        return sorted(prods, key=lambda p: p['name'])

    def ordered_products(self, ordering):
        return sorted(self.products, key=lambda p: (0, ordering.index(p['name'])) if p['name'] in ordering else (1, p['name']))

    @property
    def actions(self):
        return sorted(action_config.action_name for action_config in self.config.actions)

    def ordered_actions(self, ordering):
        return sorted(self.actions, key=lambda a: (0, ordering.index(a)) if a in ordering else (1, a))

    @property
    @memoized
    def active_location(self):
        loc_id = self.request_params.get('location_id')
        if loc_id:
            return Location.get(loc_id)

    @property
    @memoized
    def outlet_type_filter(self):
        categories = supply_point_type_categories(self.domain)
        selected = self.request.GET.getlist('outlet_type')
        if not selected:
            selected = ['_all']

        def types_for_sel(sel):
            if sel == '_oth':
                return categories['_oth']
            elif sel.startswith('cat:'):
                return categories[sel[len('cat:'):]]
            else:
                return [sel]
        active_outlet_types = reduce(lambda a, b: a.union(b), (types_for_sel(sel) for sel in selected), set())

        return lambda outlet_type: ('_all' in selected) or (outlet_type in active_outlet_types)

    @property
    @memoized
    def active_products(self):
        products = self.ordered_products(PRODUCT_ORDERING)

        selected = self.request.GET.getlist('product')
        if not selected:
            selected = ['_all']

        if '_all' in selected:
            return products
        else:
            return filter(lambda p: p['_id'] in selected, products)

    # a setting that hides supply points that have no data. mostly for PSI weirdness
    # of how they're managing their locations. don't think it's a good idea for
    # commtrack in general
    HIDE_NODATA_LOCS = True

def get_transactions(form_doc, include_inferred=True):
    from collections import Sequence
    txs = form_doc['form']['transaction']
    if not isinstance(txs, Sequence):
        txs = [txs]
    return [tx for tx in txs if include_inferred or not tx.get('@inferred')]

def get_stock_reports(domain, location, datespan):
    return [sr.raw_form for sr in \
            StockReport.get_reports(domain, location, datespan)]

def leaf_loc(form):
    return form['location_'][-1]

def child_loc(form, root):
    path = form['location_']
    ix = path.index(root._id) if root else -1
    return path[ix + 1]

HIERARCHY = [
    {
        'key': 'state',
        'caption': 'State'
    },
    {
        'key': 'district',
        'caption': 'District'
    },
    {
        'key': 'block',
        'caption': 'Block'
    },
    {
        'key': 'village',
        'caption': 'Village'
    },
]

LOC_METADATA = [
    {
        'key': 'village_class',
        'caption': 'Village Class',
        'anc_type': 'village'
    },
    {
        'key': 'village_size',
        'caption': 'Village Size',
        'anc_type': 'village'
    },
    {
        'key': 'site_code',
        'caption': 'Outlet Code',
    },
    {
        'key': 'name',
        'caption': 'Outlet',
    },
    {
        'key': 'contact_phone',
        'caption': 'Contact Phone',
    },
    {
        'key': 'outlet_type',
        'caption': 'Outlet Type',
    },
]

ACTION_ORDERING = ['stockonhand', 'sales', 'receipts', 'stockedoutfor']
PRODUCT_ORDERING = ['PSI kit', 'non-PSI kit', 'ORS', 'Zinc']

def outlet_headers(slug=False):
    return [f['key' if slug else 'caption'] for f in HIERARCHY + LOC_METADATA]

def outlet_metadata(loc, ancestors):
    lineage = dict((anc.location_type, anc) for anc in (ancestors[anc_id] for anc_id in loc.lineage))
    def loc_prop(anc_type, prop_name, default=u'\u2014'):
        l = lineage.get(anc_type) if anc_type else loc
        val = getattr(l, prop_name, default) if l else default

        # hack to keep stock report export for old data working
        if prop_name == 'site_code' and val == default:
            try:
                startkey = [loc.domain, loc._id]
                supply_point = CommCareCase.view('commtrack/supply_point_by_loc',
                                                 startkey=startkey,
                                                 endkey=startkey + [{}],
                                                 include_docs=True).one()
                val = supply_point.site_code
            except Exception:
                val = '**ERROR**'
        # end hack

        return val

    row = []
    row += [loc_prop(f['key'], 'name') for f in HIERARCHY]
    row += [loc_prop(f.get('anc_type'), f['key']) for f in LOC_METADATA]
    return row

def load_locs(loc_ids):
    return dict((loc._id, loc) for loc in Location.view('_all_docs', keys=list(loc_ids), include_docs=True))

def load_all_loc_hierarchy(locs):
    ancestor_loc_ids = reduce(lambda a, b: a.union(b), (loc.lineage for loc in locs), set())
    return load_locs(ancestor_loc_ids)

class VisitReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Visit Report'
    slug = 'visits'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    def header_text(self, slug=False):
        cols = outlet_headers(slug)
        cols.extend([
            ('date' if slug else 'Date'),
            ('reporter' if slug else 'Reporter'),
        ])
        cfg = self.config
        for p in self.active_products:
            for a in self.ordered_actions(ACTION_ORDERING):
                if slug:
                    cols.append('data: %s %s' % (cfg.actions_by_name[a].keyword, p['code']))
                else:
                    cols.append('%s (%s)' % (cfg.actions_by_name[a].caption, p['name']))

        return cols

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in self.header_text()))

    @property
    def rows(self):
        products = self.active_products
        reports = get_stock_reports(self.domain, self.active_location, self.datespan)
        locs = load_locs(leaf_loc(r) for r in reports)
        ancestry = load_all_loc_hierarchy(locs.values())

        # filter by outlet type
        reports = filter(lambda r: self.outlet_type_filter(locs[leaf_loc(r)].outlet_type), reports)

        def row(doc):
            transactions = dict(((tx['action'], tx['product']), tx['value']) for tx in get_transactions(doc, False))
            location = locs[leaf_loc(doc)]

            data = outlet_metadata(location, ancestry)
            data.extend([
                dateparse.string_to_datetime(doc['received_on']).strftime('%Y-%m-%d'),
                CommCareUser.get(doc['form']['meta']['userID']).username_in_report,
            ])
            for p in products:
                for a in self.ordered_actions(ACTION_ORDERING):
                    data.append(transactions.get((a, p['_id']), u'\u2014'))

            return data

        return [row(r) for r in reports]

class StockReportExport(VisitReport):
    name = 'Stock Reports Export'
    slug = 'bulk_export'
    exportable = True
    emailable = False

    @property
    def export_table(self):
        headers = self.header_text(slug=True)
        rows = [headers]
        rows.extend(self.rows)

        exclude_cols = set()
        for i, h in enumerate(headers):
            if not (h.startswith('data:') or h in ('site_code', 'reporter', 'date')):
                exclude_cols.add(i)

        def clean_cell(val):
            dashes = set(['-', '--']).union(unichr(c) for c in range(0x2012, 0x2016))
            return '' if val in dashes else val

        def filter_row(row):
            return [clean_cell(c) for i, c in enumerate(row) if i not in exclude_cols]

        return [['stock reports', [filter_row(r) for r in rows]]]

OUTLETS_LIMIT = 500

class SalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Sales and Consumption Report'
    slug = 'sales_consumption'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.commtrack.fields.ProductField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    @property
    @memoized
    def outlets(self):
        locs = Location.filter_by_type(self.domain, 'outlet', self.active_location)
        locs = filter(lambda loc: self.outlet_type_filter(loc.outlet_type), locs)
        return locs

    @property
    @memoized
    def ancestry(self):
        return load_all_loc_hierarchy(self.outlets)

    @property
    def headers(self):
        if len(self.outlets) > OUTLETS_LIMIT:
            return DataTablesHeader(DataTablesColumn('Too many outlets'))

        cols = outlet_headers()
        for p in self.active_products:
            cols.append('Stock on Hand (%s)' % p['name'])
            cols.append('Total Sales (%s)' % p['name'])
            cols.append('Total Consumption (%s)' % p['name'])
        cols.append('Stock-out days (all products combined)')

        return DataTablesHeader(*(DataTablesColumn(c) for c in cols))

    @property
    def rows(self):
        if len(self.outlets) > OUTLETS_LIMIT:
            return [[
                    'This report is limited to <b>%(max)d</b> outlets. Your location filter includes <b>%(count)d</b> outlets. Please make your location filter more specific.' % {
                        'count': len(self.outlets),
                        'max': OUTLETS_LIMIT,
                }]]

        products = self.active_products
        reports = get_stock_reports(self.domain, self.active_location, self.datespan)
        reports_by_loc = map_reduce(lambda e: [(leaf_loc(e),)], data=reports, include_docs=True)

        def summary_row(site, reports):
            all_transactions = list(itertools.chain(*(get_transactions(r) for r in reports)))
            tx_by_product = map_reduce(lambda tx: [(tx['product'],)], data=all_transactions, include_docs=True)

            data = outlet_metadata(site, self.ancestry)
            stockouts = {}
            inactive_site = True
            for p in products:
                tx_by_action = map_reduce(lambda tx: [(tx['action'], int(tx['value']))], data=tx_by_product.get(p['_id'], []))

                startkey = [str(self.domain), site._id, p['_id'], dateparse.json_format_datetime(self.datespan.startdate)]
                endkey =   [str(self.domain), site._id, p['_id'], dateparse.json_format_datetime(self.datespan.end_of_end_day)]

                # list() is necessary or else get a weird error
                product_states = list(get_db().view('commtrack/stock_product_state', startkey=startkey, endkey=endkey))
                latest_state = product_states[-1]['value'] if product_states else None
                if latest_state:
                    stock = latest_state['updated_unknown_properties']['current_stock']
                    as_of = dateparse.string_to_datetime(latest_state['server_date']).strftime('%Y-%m-%d')
                    inactive_site = False

                stockout_dates = set()
                for state in product_states:
                    doc = state['value']
                    stocked_out_since = doc['updated_unknown_properties']['stocked_out_since']
                    if stocked_out_since:
                        so_start = max(dateparse.string_to_datetime(stocked_out_since).date(), self.datespan.startdate.date())
                        so_end = dateparse.string_to_datetime(doc['server_date']).date() # TODO deal with time zone issues
                        dt = so_start
                        while dt < so_end:
                            stockout_dates.add(dt)
                            dt += timedelta(days=1)
                stockouts[p['_id']] = stockout_dates

                data.append('%s (%s)' % (stock, as_of) if latest_state else u'\u2014')
                data.append(sum(tx_by_action.get('sales', [])))
                data.append(sum(tx_by_action.get('consumption', [])))

            combined_stockout_days = len(reduce(lambda a, b: a.intersection(b), stockouts.values()))
            data.append(combined_stockout_days)

            if self.HIDE_NODATA_LOCS and inactive_site:
                return None

            return data

        return filter(None, (summary_row(site, reports_by_loc.get(site._id, [])) for site in self.outlets))

class CumulativeSalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Sales and Consumption Report, Cumulative'
    slug = 'cumul_sales_consumption'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.commtrack.fields.ProductField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    agg_type = 'village'

    # TODO support aggregation by 'N-levels down' (the locations at which might have varying loc types) as well as by subloc type?

    @memoized
    def _descendants(self, loc_type=None):
        locs = self.active_location.descendants if self.active_location else all_locations(self.domain)
        return filter(lambda loc: loc_type is None or loc.location_type == loc_type, locs)

    @property
    def aggregation_locs(self):
        return self._descendants(self.agg_type)

    @property
    def leaf_locs(self):
        return self._descendants('outlet')

    @property
    def headers(self):
        if not self.aggregation_locs:
            return DataTablesHeader(DataTablesColumn('No locations'))

        cols = [
            DataTablesColumn('Location'),
            DataTablesColumn('Location Type'),
            DataTablesColumn('# reporting outlets'),
        ]
        for p in self.active_products:
            cols.append(DataTablesColumn('Total Stock on Hand (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Sales (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Consumption (%s)' % p['name']))

        return DataTablesHeader(*cols)

    @property
    def rows(self):
        if not self.aggregation_locs:
            return [['There are no locations of type "%s" inside the selected location. Choose an administrative location higher up in the hierarchy.' % self.agg_type]]

        products = self.active_products
        locs = self.aggregation_locs
        active_outlets = [loc for loc in self.leaf_locs if self.outlet_type_filter(loc.dynamic_properties().get('outlet_type'))]

        active_outlet_ids = set(loc._id for loc in active_outlets)
        aggregation_sites = set(loc._id for loc in locs)

        def get_aggregation_site(outlet):
            for k in outlet.path:
                if k in aggregation_sites:
                    return k
        outlets_by_aggregation_site = map_reduce(lambda e: [(get_aggregation_site(e),)], data=active_outlets)

        reports = filter(lambda r: leaf_loc(r) in active_outlet_ids, get_stock_reports(self.domain, self.active_location, self.datespan))
        def get_aggregators(report):
            for k in report['location_']:
                if k in aggregation_sites:
                    yield (k,)
        reports_by_loc = map_reduce(get_aggregators, data=reports, include_docs=True)

        startkey = [self.domain, self.active_location._id if self.active_location else None, 'CommCareCase']
        product_cases = [c for c in CommCareCase.view('locations/linked_docs', startkey=startkey, endkey=startkey + [{}], include_docs=True)
                         if c.type == 'supply-point-product' and leaf_loc(c) in active_outlet_ids]
        product_cases_by_parent = map_reduce(get_aggregators, data=product_cases, include_docs=True)

        def summary_row(site, reports, product_cases, outlets):
            all_transactions = list(itertools.chain(*(get_transactions(r) for r in reports)))
            tx_by_product = map_reduce(lambda tx: [(tx['product'],)], data=all_transactions, include_docs=True)
            cases_by_product = map_reduce(lambda c: [(c.product,)], data=product_cases, include_docs=True)

            num_outlets = len(outlets)
            num_active_outlets = len(set(leaf_loc(r) for r in reports))

            # feels not DRY
            import urllib
            site_url = '%s?%s' % (self.get_url(self.domain), urllib.urlencode({
                'startdate': self.datespan.startdate_display,
                'enddate': self.datespan.enddate_display,
                'location_id': site._id,
            }))
            site_link = '<a href="%s">%s</a>' % (site_url, site.name)
            data = [
                site_link,
                site.location_type,
                '%d of %d' % (num_active_outlets, num_outlets),
            ]
            for p in products:
                tx_by_action = map_reduce(lambda tx: [(tx['action'], int(tx['value']))], data=tx_by_product.get(p['_id'], []))
                subcases = cases_by_product.get(p['_id'], [])
                stocks = [int(k) for k in (c.get_case_property('current_stock') for c in subcases) if k is not None]

                data.append(sum(stocks) if stocks else u'\u2014')
                data.append(sum(tx_by_action.get('sales', [])))
                data.append(sum(tx_by_action.get('consumption', [])))

            return data

        return [summary_row(site,
                            reports_by_loc.get(site._id, []),
                            product_cases_by_parent.get(site._id, []),
                            outlets_by_aggregation_site.get(site._id, []),
                        ) for site in locs]

class StockOutReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Stock-out Report'
    slug = 'stockouts'
    fields = ['corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.commtrack.fields.ProductField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    # TODO shared code with sales/consumption report (any report that reports one line
    # per supply point) could be factored out into mixin
    @property
    @memoized
    def outlets(self):
        locs = Location.filter_by_type(self.domain, 'outlet', self.active_location)
        locs = filter(lambda loc: self.outlet_type_filter(loc.outlet_type), locs)
        return locs

    @property
    @memoized
    def ancestry(self):
        return load_all_loc_hierarchy(self.outlets)

    @property
    def headers(self):
        if len(self.outlets) > OUTLETS_LIMIT:
            return DataTablesHeader(DataTablesColumn('Too many outlets'))

        cols = outlet_headers()
        for p in self.active_products:
            cols.append('%s: Days stocked out' % p['name'])
        cols.append('All Products Combined: Days stocked out')
        return DataTablesHeader(*(DataTablesColumn(c) for c in cols))

    @property
    def rows(self):
        if len(self.outlets) > OUTLETS_LIMIT:
            return [['This report is limited to <b>%(max)d</b> outlets. Your location filter includes <b>%(count)d</b> outlets. Please make your location filter more specific.' % {
                        'count': len(self.outlets),
                        'max': OUTLETS_LIMIT,
                    }]]

        products = self.active_products
        def row(site):
            data = outlet_metadata(site, self.ancestry)

            stockout_days = []
            inactive_site = True
            for p in products:
                startkey = [str(self.domain), site._id, p['_id']]
                endkey = startkey + [{}]

                latest_state = get_db().view('commtrack/stock_product_state', startkey=endkey, endkey=startkey, descending=True).first()
                if latest_state:
                    doc = latest_state['value']
                    so_date = doc['updated_unknown_properties']['stocked_out_since']
                    if so_date:
                        so_days = (date.today() - dateparse.string_to_datetime(so_date).date()).days + 1
                    else:
                        so_days = 0
                    inactive_site = False
                else:
                    so_days = None

                if so_days is not None:
                    stockout_days.append(so_days)
                    data.append(so_days)
                else:
                    data.append(u'\u2014')

            combined_stockout_days = min(stockout_days) if stockout_days else None
            data.append(combined_stockout_days if combined_stockout_days is not None else u'\u2014')

            if self.HIDE_NODATA_LOCS and inactive_site:
                return None
            
            return data

        return filter(None, (row(site) for site in self.outlets))

