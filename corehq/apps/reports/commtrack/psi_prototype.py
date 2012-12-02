from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.commtrack.models import *
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.locations.models import Location
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils import parsing as dateparse
import itertools
from datetime import datetime, date, timedelta

class CommtrackReportMixin(ProjectReport, ProjectReportParametersMixin):

    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        domain = Domain.get_by_name(kwargs['domain'])
        return domain.commtrack_enabled
    
    @property
    def config(self):
        return CommtrackConfig.for_domain(self.domain)

    @property
    def products(self):
        query = get_db().view('commtrack/products', startkey=[self.domain], endkey=[self.domain, {}], include_docs=True)
        prods = [e['doc'] for e in query]
        return sorted(prods, key=lambda p: p['name'])

    def ordered_products(self, ordering):
        return sorted(self.products, key=lambda p: (0, ordering.index(p['name'])) if p['name'] in ordering else (1, p['name']))

    @property
    def actions(self):
        return sorted(action_config.action_name for action_config in self.config.actions)

    def ordered_actions(self, ordering):
        return sorted(self.actions, key=lambda a: (0, ordering.index(a)) if a in ordering else (1, a))

    # find a memoize decorator?
    _location = None
    @property
    def active_location(self):
        if not self._location:
            loc_id = self.request_params.get('location_id')
            if loc_id:
                self._location = Location.get(loc_id)
        return self._location

def get_transactions(form_doc, include_inferred=True):
    from collections import Sequence
    txs = form_doc['form']['transaction']
    if not isinstance(txs, Sequence):
        txs = [txs]
    return [tx for tx in txs if include_inferred or not tx.get('@inferred')]

def get_stock_reports(domain, location, datespan):
    timestamp_start = dateparse.json_format_datetime(datespan.startdate)
    timestamp_end =  dateparse.json_format_datetime(datespan.end_of_end_day)
    loc_id = location._id if location else None

    startkey = [domain, loc_id, timestamp_start]
    endkey = [domain, loc_id, timestamp_end]

    query = get_db().view('commtrack/stock_reports', startkey=startkey, endkey=endkey, include_docs=True)
    return [e['doc'] for e in query]

def leaf_loc(form):
    return form['location_'][-1]

OUTLET_METADATA = [
    ('state', 'State'),
    ('district', 'District'),
    ('block', 'Block'),
    ('village', 'Village'),
    ('outlet_id', 'Outlet ID'),
    ('name', 'Outlet'),
    ('contact_phone', 'Contact Phone'),
    ('outlet_type', 'Outlet Type'),
]

ACTION_ORDERING = ['stockonhand', 'sales', 'receipts', 'stockedoutfor']
PRODUCT_ORDERING = ['PSI kit', 'non-PSI kit', 'ORS', 'Zinc']

class VisitReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Visit Report'
    slug = 'visits'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.fields.LocationField']

    def header_text(self, slug=False):
        cols = [(key if slug else caption) for key, caption in OUTLET_METADATA]
        cols.extend([
            ('date' if slug else 'Date'),
            ('reporter' if slug else 'Reporter'),
        ])
        cfg = self.config
        for p in self.ordered_products(PRODUCT_ORDERING):
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
        products = self.ordered_products(PRODUCT_ORDERING)
        reports = get_stock_reports(self.domain, self.active_location, self.datespan)
        locs = dict((loc._id, loc) for loc in Location.view('_all_docs', keys=[leaf_loc(r) for r in reports], include_docs=True))

        def row(doc):
            transactions = dict(((tx['action'], tx['product']), tx['value']) for tx in get_transactions(doc, False))
            location =  locs[leaf_loc(doc)]

            data = [getattr(location, key) for key, caption in OUTLET_METADATA]
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

    @property
    def export_table(self):
        headers = self.header_text(slug=True)
        rows = [headers]
        rows.extend(self.rows)

        exclude_cols = set()
        for i, h in enumerate(headers):
            if not (h.startswith('data:') or h in ('outlet_id', 'reporter', 'date')):
                exclude_cols.add(i)

        def clean_cell(val):
            dashes = set(['-', '--']).union(unichr(c) for c in range(0x2012, 0x2016))
            return '' if val in dashes else val

        def filter_row(row):
            return [clean_cell(c) for i, c in enumerate(row) if i not in exclude_cols]

        return [['stock reports', [filter_row(r) for r in rows]]]

class SalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    OUTLETS_LIMIT = 200

    name = 'Sales and Consumption Report'
    slug = 'sales_consumption'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.fields.LocationField']

    @property
    def outlets(self):
        if not hasattr(self, '_locs'):
            self._locs = Location.filter_by_type(self.domain, 'outlet', self.active_location)
        return self._locs

    @property
    def headers(self):
        if len(self.outlets) > self.OUTLETS_LIMIT:
            return DataTablesHeader(DataTablesColumn('Too many outlets'))

        cols = [DataTablesColumn(caption) for key, caption in OUTLET_METADATA]
        for p in self.ordered_products(PRODUCT_ORDERING):
            cols.append(DataTablesColumn('Stock on Hand (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Sales (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Consumption (%s)' % p['name']))
        cols.append(DataTablesColumn('Stock-out days (all products combined)'))

        return DataTablesHeader(*cols)

    @property
    def rows(self):
        if len(self.outlets) > self.OUTLETS_LIMIT:
            return [[
                    'This report is limited to <b>%(max)d</b> outlets. Your location filter includes <b>%(count)d</b> outlets. Please make your location filter more specific.' % {
                        'count': len(self.outlets),
                        'max': self.OUTLETS_LIMIT,
                }]]

        products = self.ordered_products(PRODUCT_ORDERING)
        locs = Location.filter_by_type(self.domain, 'outlet', self.active_location)
        reports = get_stock_reports(self.domain, self.active_location, self.datespan)
        reports_by_loc = map_reduce(lambda e: [(leaf_loc(e),)], data=reports, include_docs=True)

        def summary_row(site, reports):
            all_transactions = list(itertools.chain(*(get_transactions(r) for r in reports)))
            tx_by_product = map_reduce(lambda tx: [(tx['product'],)], data=all_transactions, include_docs=True)

            data = [getattr(site, key) for key, caption in OUTLET_METADATA]
            stockouts = {}
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

            return data

        return [summary_row(site, reports_by_loc.get(site._id, [])) for site in locs]
