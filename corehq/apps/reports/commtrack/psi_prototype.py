from django.conf import settings
from django.utils.translation import ugettext_noop
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.fields import ReportField, AsyncDrillableField
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.domain.models import Domain
from corehq.apps.reports.util import make_form_couch_key
from corehq.apps.users.models import CommCareUser
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.locations.models import Location
from couchforms.models import XFormInstance
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
    def active_outlet_types(self):
        categories = supply_point_type_categories(self.domain)
        selected = self.request.GET.getlist('outlet_type')
        if not selected:
            selected = ['_all']

        def types_for_sel(sel):
            if sel == '_all':
                return itertools.chain(*categories.values())
            elif sel == '_oth':
                return categories['_oth']
            elif sel.startswith('cat:'):
                return categories[sel[len('cat:'):]]
            else:
                return [sel]
        return reduce(lambda a, b: a.union(b), (types_for_sel(sel) for sel in selected), set())

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
    return path[path.index(root._id) + 1]

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
              'corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True

    def header_text(self, slug=False):
        cols = [(key if slug else caption) for key, caption in OUTLET_METADATA]
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
        locs = dict((loc._id, loc) for loc in Location.view('_all_docs', keys=[leaf_loc(r) for r in reports], include_docs=True))

        # filter by outlet type
        reports = filter(lambda r: locs[leaf_loc(r)].outlet_type in self.active_outlet_types, reports)

        def row(doc):
            transactions = dict(((tx['action'], tx['product']), tx['value']) for tx in get_transactions(doc, False))
            location = locs[leaf_loc(doc)]

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
    exportable = True

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

OUTLETS_LIMIT = 200

class SalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Sales and Consumption Report'
    slug = 'sales_consumption'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.commtrack.fields.ProductField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True

    @property
    @memoized
    def outlets(self):
        locs = Location.filter_by_type(self.domain, 'outlet', self.active_location)
        locs = [loc for loc in locs if loc.outlet_type in self.active_outlet_types]
        return locs

    @property
    def headers(self):
        if len(self.outlets) > OUTLETS_LIMIT:
            return DataTablesHeader(DataTablesColumn('Too many outlets'))

        cols = [DataTablesColumn(caption) for key, caption in OUTLET_METADATA]
        for p in self.active_products:
            cols.append(DataTablesColumn('Stock on Hand (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Sales (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Consumption (%s)' % p['name']))
        cols.append(DataTablesColumn('Stock-out days (all products combined)'))

        return DataTablesHeader(*cols)

    @property
    def rows(self):
        if len(self.outlets) > OUTLETS_LIMIT:
            return [[
                    'This report is limited to <b>%(max)d</b> outlets. Your location filter includes <b>%(count)d</b> outlets. Please make your location filter more specific.' % {
                        'count': len(self.outlets),
                        'max': OUTLETS_LIMIT,
                }]]

        products = self.active_products
        locs = self.outlets
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

class CumulativeSalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Sales and Consumption Report, Cumulative'
    slug = 'cumul_sales_consumption'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.commtrack.fields.ProductField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True

    @property
    @memoized
    def children(self):
        return self.active_location.children if self.active_location else []

    @property
    def headers(self):
        if not self.children:
            return DataTablesHeader(DataTablesColumn('No locations'))

        cols = [
            DataTablesColumn('Location'),
            DataTablesColumn('Location Type'),
        ]
        for p in self.active_products:
            cols.append(DataTablesColumn('Total Stock on Hand (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Sales (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Consumption (%s)' % p['name']))

        return DataTablesHeader(*cols)

    @property
    def rows(self):
        if not self.children:
            return [['The location you\'ve chosen has no member locations. Choose an administrative location higher up in the hierarchy.']]

        products = self.active_products
        locs = self.children
        active_outlets = set(loc._id for loc in self.active_location.descendants if loc.dynamic_properties().get('outlet_type') in self.active_outlet_types)

        reports = filter(lambda r: leaf_loc(r) in active_outlets, get_stock_reports(self.domain, self.active_location, self.datespan))
        reports_by_loc = map_reduce(lambda e: [(child_loc(e, self.active_location),)], data=reports, include_docs=True)

        startkey = [self.domain, self.active_location._id, 'CommCareCase']
        product_cases = [c for c in CommCareCase.view('locations/linked_docs', startkey=startkey, endkey=startkey + [{}], include_docs=True)
                         if c.type == 'supply-point-product' and leaf_loc(c) in active_outlets]
        product_cases_by_parent = map_reduce(lambda e: [(child_loc(e, self.active_location),)], data=product_cases, include_docs=True)

        def summary_row(site, reports, product_cases):
            all_transactions = list(itertools.chain(*(get_transactions(r) for r in reports)))
            tx_by_product = map_reduce(lambda tx: [(tx['product'],)], data=all_transactions, include_docs=True)
            cases_by_product = map_reduce(lambda c: [(c.product,)], data=product_cases, include_docs=True)

            # feels not DRY
            import urllib
            site_url = '%s?%s' % (self.get_url(self.domain), urllib.urlencode({
                'startdate': self.datespan.startdate_display,
                'enddate': self.datespan.enddate_display,
                'location_id': site._id,
            }))
            site_link = '<a href="%s">%s</a>' % (site_url, site.name)
            data = [site_link, site.location_type]
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
                            product_cases_by_parent.get(site._id, [])) for site in locs]

class StockOutReport(GenericTabularReport, CommtrackReportMixin, DatespanMixin):
    name = 'Stock-out Report'
    slug = 'stockouts'
    fields = ['corehq.apps.reports.commtrack.fields.SupplyPointTypeField',
              'corehq.apps.reports.commtrack.fields.ProductField',
              'corehq.apps.reports.fields.AsyncLocationField']
    exportable = True

    # TODO shared code with sales/consumption report (any report that reports one line
    # per supply point) could be factored out into mixin
    @property
    @memoized
    def outlets(self):
        locs = Location.filter_by_type(self.domain, 'outlet', self.active_location)
        locs = [loc for loc in locs if loc.outlet_type in self.active_outlet_types]
        return locs

    @property
    def headers(self):
        if len(self.outlets) > OUTLETS_LIMIT:
            return DataTablesHeader(DataTablesColumn('Too many outlets'))

        cols = [caption for key, caption in OUTLET_METADATA]
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
            data = [getattr(site, key) for key, caption in OUTLET_METADATA]

            stockout_days = []
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
                else:
                    so_days = None

                if so_days is not None:
                    stockout_days.append(so_days)
                    data.append(so_days)
                else:
                    data.append(u'\u2014')

            combined_stockout_days = min(stockout_days) if stockout_days else None
            data.append(combined_stockout_days if combined_stockout_days is not None else u'\u2014')

            return data

        return [row(site) for site in self.outlets]

def _get_unique_combinations(domain, place_types=None, place_id=None):
    if not place_types:
        return []
    if place_id:
        place_type_from_id = place_id.split(':')[0]
        place_name = place_id.split(':')[1].lower()

    place_data_types = {}
    for pt in place_types:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()

    relevant_types =  [t for t in ["village", "block", "district", "state"] if t in place_types]
    base_type = relevant_types[0] if relevant_types else ""
    fdis = FixtureDataItem.by_data_type(domain, place_data_types[base_type].get_id) if base_type else []

    combos = []
    for fdi in fdis:
        if place_id:
            if base_type == place_type_from_id:
                if fdi.fields['name'].lower() != place_name:
                    continue
            else:
                if fdi.fields.get(place_type_from_id+"_id", "").lower() != place_name:
                    continue
        comb = {}
        for pt in place_types:
            if base_type == pt:
                comb[pt] = fdi.fields['name'].lower()
            else:
                p_id = fdi.fields.get(pt+"_id", None)
                if p_id:
                    if place_id and pt == place_type_from_id and p_id != place_name:
                        continue
                    comb[pt] = p_id
                else:
                    comb[pt] = None
        combos.append(comb)

    return combos

def psi_events(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['state', 'district']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: event_stats(domain, c, query_dict.get("location", ""), startdate=startdate, enddate=enddate), combos)

def event_stats(domain, place_dict, location="", startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Plays and Events':
            return False
        if place_dict["state"] and form.xpath('form/activity_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/activity_district') != place_dict["district"]:
            return False
        if location:
            if not form.xpath('form/event_location') == location:
                return False
        return True

    forms = list(_get_forms(domain, form_filter=ff_func, startdate=startdate, enddate=enddate))
    place_dict.update({
        "location": location,
        "num_male": reduce(lambda sum, f: sum + f.xpath('form/number_of_males'), forms, 0),
        "num_female": reduce(lambda sum, f: sum + f.xpath('form/number_of_females'), forms, 0),
        "num_total": reduce(lambda sum, f: sum + f.xpath('form/number_of_attendees'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + f.xpath('form/number_of_leaflets'), forms, 0),
        "num_gifts": reduce(lambda sum, f: sum + f.xpath('form/number_of_gifts'), forms, 0)
    })
    return place_dict

def psi_household_demonstrations(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['block', 'state', 'district', 'village']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: hd_stats(domain, c, query_dict.get("worker_type", ""), startdate=startdate, enddate=enddate), combos)

def hd_stats(domain, place_dict, worker_type="", startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Household Demonstration':
            return False
        if place_dict["state"] and form.xpath('form/activity_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/activity_district') != place_dict["district"]:
            return False
        if place_dict["block"] and form.xpath('form/activity_block') != place_dict["block"]:
            return False
        if place_dict["village"] and form.xpath('form/activity_village') != place_dict["village"]:
            return False
        if worker_type:
            if not form.xpath('form/demo_type') == worker_type:
                return False
        return True

    forms = list(_get_forms(domain, form_filter=ff_func, startdate=startdate, enddate=enddate))
    place_dict.update({
        "worker_type": worker_type,
        "num_hh_demo": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'hh_covered'), forms, 0),
        "num_young": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'number_young_children_covered'), forms, 0),
        "num_leaflets": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'leaflets_distributed'), forms, 0),
        "num_kits": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/visits'), 'kits_sold'), forms, 0),
        })
    return place_dict

def psi_sensitization_sessions(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['state', 'district', 'block']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: ss_stats(domain, c, startdate=startdate, enddate=enddate), combos)

def ss_stats(domain, place_dict, startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Sensitization Session':
            return False
        if place_dict["state"] and form.xpath('form/training_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/training_district') != place_dict["district"]:
            return False
        if place_dict["block"] and form.xpath('form/training_block') != place_dict["block"]:
            return False
        return True

    forms = list(_get_forms(domain, form_filter=ff_func, startdate=startdate, enddate=enddate))

    def rf_func(data):
        return data.get('type_of_sensitization', None) == 'vhnd'

    place_dict.update({
        "num_sessions": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'number_of_blm_attended'), forms, 0) +
                        reduce(lambda sum, f: sum + len(list(_get_repeats(f.xpath('form/training_sessions'), repeat_filter=rf_func))), forms, 0),
        "num_ayush_doctors": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_ayush_doctors'), forms, 0),
        "num_mbbs_doctors": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_mbbs_doctors'), forms, 0),
        "num_asha_supervisors": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_asha_supervisors'), forms, 0),
        "num_ashas": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_ashas'), forms, 0),
        "num_awws": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_awws'), forms, 0),
        "num_other": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'num_other'), forms, 0),
        "number_attendees": reduce(lambda sum, f: sum + _count_in_repeats(f.xpath('form/training_sessions'), 'number_attendees'), forms, 0),
        })
    return place_dict


def psi_training_sessions(domain, query_dict, startdate=None, enddate=None, place_id=None):
    place_types = ['state', 'district']
    combos = _get_unique_combinations(domain, place_types=place_types, place_id=place_id)
    return map(lambda c: ts_stats(domain, c, query_dict.get("training_type", ""), startdate=startdate, enddate=enddate), combos)

def ts_stats(domain, place_dict, training_type="", startdate=None, enddate=None):
    def ff_func(form):
        if form.form.get('@name', None) != 'Training Session':
            return False
        if place_dict["state"] and form.xpath('form/training_state') != place_dict["state"]:
            return False
        if place_dict["district"] and form.xpath('form/training_district') != place_dict["district"]:
            return False
        if training_type:
            if not form.xpath('form/training_type') == training_type:
                return False
        return True

    forms = list(_get_forms(domain, form_filter=ff_func, startdate=startdate, enddate=enddate))

    all_forms = list(_get_forms(domain, form_filter=lambda f: f.form.get('@name', None) == 'Training Session'))
    private_forms = filter(lambda f: f.xpath('form/trainee_category') == 'private', forms)
    public_forms = filter(lambda f: f.xpath('form/trainee_category') == 'public', forms)
    dh_forms = filter(lambda f: f.xpath('form/trainee_category') == 'depot_holder', forms)
    flw_forms = filter(lambda f: f.xpath('form/trainee_category') == 'flw_training', forms)

    place_dict.update({
        "training_type": training_type,
        "private_hcp": _indicators(private_forms, aa=True),
        "public_hcp": _indicators(public_forms, aa=True),
        "depot_training": _indicators(dh_forms),
        "flw_training": _indicators(flw_forms),
        })
    return place_dict

def _indicators(forms, aa=False):
    ret = { "num_forms": len(forms),
            "num_trained": _num_trained(forms)}
    if aa:
        ret.update({
            "num_ayush_trained": _num_trained(forms, doctor_type="ayush"),
            "num_allopathics_trained": _num_trained(forms, doctor_type="allopathic"),
            })
    ret.update(_scores(forms))
    return ret

def _num_trained(forms, doctor_type=None):
    def rf_func(data):
        if data:
            return data.get('doctor_type', None) == doctor_type if doctor_type else True
        else:
            return False
    return reduce(lambda sum, f: sum + len(list(_get_repeats(f.xpath('form/trainee_information'), repeat_filter=rf_func))), forms, 0)

def _scores(forms):
    trainees = []

    for f in forms:
        trainees.extend(list(_get_repeats(f.xpath('form/trainee_information'))))

    trainees = filter(lambda t: t, trainees)
    total_pre_scores = reduce(lambda sum, t: sum + int(t.get("pre_test_score", 0) or 0), trainees, 0)
    total_post_scores = reduce(lambda sum, t: sum + int(t.get("post_test_score", 0) or 0), trainees, 0)
    total_diffs = reduce(lambda sum, t: sum + (int(t.get("post_test_score", 0) or 0) - int(t.get("pre_test_score", 0) or 0)), trainees, 0)

    return {
        "avg_pre_score": total_pre_scores/len(trainees) if trainees else "No Data",
        "avg_post_score": total_post_scores/len(trainees) if trainees else "No Data",
        "avg_difference": total_diffs/len(trainees) if trainees else "No Data",
        "num_gt80": len(filter(lambda t: t.get("post_test_score", 0) or 0 >= 80.0, trainees))/len(trainees) if trainees else "No Data"
    }

def _get_repeats(data, repeat_filter=lambda r: True):
    if not isinstance(data, list):
        data = [data]
    for d in data:
        if repeat_filter(d):
            yield d

def _count_in_repeats(data, what_to_count):
    if not isinstance(data, list):
        data = [data]
    return reduce(lambda sum, d: sum + int(d.get(what_to_count, 0) or 0), data, 0)

def _get_all_form_submissions(domain, startdate=None, enddate=None):
    key = make_form_couch_key(domain)
    startkey = key+[startdate] if startdate and enddate else key
    endkey = key+[enddate] if startdate and enddate else key + [{}]
    submissions = XFormInstance.view('reports_forms/all_forms',
        startkey=startkey,
        endkey=endkey,
        include_docs=True,
        reduce=False
    )
    return submissions


def _get_forms(domain, form_filter=lambda f: True, startdate=None, enddate=None):
    for form in _get_all_form_submissions(domain, startdate=startdate, enddate=enddate):
        if form_filter(form):
            yield form

def _get_form(domain, action_filter=lambda a: True, form_filter=lambda f: True):
    """
    returns the first form that passes through the form filter function
    """
    gf = _get_forms(domain, form_filter=form_filter)
    try:
        return gf.next()
    except StopIteration:
        return None

class AsyncPlaceField(AsyncDrillableField):
    name = "Place"
    slug = "new_place"
    hierarchy = [{"type": "state", "display": "name"},
                 {"type": "district", "parent_ref": "state_id", "references": "id", "display": "name"},
                 {"type": "block", "parent_ref": "district_id", "references": "id", "display": "name"},
                 {"type": "village", "parent_ref": "block_id", "references": "id", "display": "name"}]

class PSIReport(GenericTabularReport, CustomProjectReport, DatespanMixin):
    fields = ['corehq.apps.reports.fields.DatespanField','corehq.apps.reports.commtrack.psi_prototype.AsyncPlaceField',]

class PSIEventsReport(PSIReport):
    name = "Event Demonstration Report"
    slug = "event_demonstations"
    section_name = "event demonstrations"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Location"),
            DataTablesColumn("Number of male attendees"),
            DataTablesColumn("Number of female attendees"),
            DataTablesColumn("Total number of attendees"),
            DataTablesColumn("Total number of leaflets distributed"),
            DataTablesColumn("Total number of gifts distributed"))

    @property
    def rows(self):
        event_data = psi_events(self.domain, {}, place_id=self.request.GET.get('location_id', ""),
            startdate=self.datespan.startdate_param_utc, enddate=self.datespan.enddate_param_utc)
        for d in event_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("location"),
                d.get("num_male"),
                d.get("num_female") ,
                d.get("num_total"),
                d.get("num_leaflets"),
                d.get("num_gifts")
            ]

class PSIHDReport(PSIReport):
    name = "Household Demonstrations Report"
    slug = "household_demonstations"
    section_name = "household demonstrations"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Name of Block"),
            DataTablesColumn("Name of Town/Village"),
            DataTablesColumn("Number of HH demos done"),
            DataTablesColumn("Demonstration done by"),
            DataTablesColumn("Number of 0-6 year old children"),
            DataTablesColumn("Number of leaflets distributed"),
            DataTablesColumn("Number of kits sold"))

    @property
    def rows(self):
        hh_data = psi_household_demonstrations(self.domain, {}, place_id=self.request.GET.get('location_id', ""),
            startdate=self.datespan.startdate_param_utc, enddate=self.datespan.enddate_param_utc)
        for d in hh_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("block"),
                d.get("village"),
                d.get("num_hh_demo") ,
                d.get("worker_type"),
                d.get("num_young"),
                d.get("num_leaflets"),
                d.get("num_kits"),
                ]

class PSISSReport(PSIReport):
    name = "Sensitization Sessions Report"
    slug = "sensitization_sessions"
    section_name = "sensitization sessions"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Name of Block"),
            DataTablesColumn("Number of Sessions"),
            DataTablesColumn("Ayush Trained"),
            DataTablesColumn("MBBS Trained"),
            DataTablesColumn("Asha Supervisors Trained"),
            DataTablesColumn("Ashas Trained"),
            DataTablesColumn("AWW Trained"),
            DataTablesColumn("Other Trained"),
            DataTablesColumn("VHND Attendees"))

    @property
    def rows(self):
        hh_data = psi_sensitization_sessions(self.domain, {}, place_id=self.request.GET.get('location_id', ""),
            startdate=self.datespan.startdate_param_utc, enddate=self.datespan.enddate_param_utc)
        for d in hh_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("block"),
                d.get("num_sessions") ,
                d.get("num_ayush_doctors"),
                d.get("num_mbbs_doctors"),
                d.get("num_asha_supervisors"),
                d.get("num_ashas"),
                d.get("num_awws"),
                d.get("num_other"),
                d.get("number_attendees"),
                ]

class PSITSReport(PSIReport):
    name = "Training Sessions Report"
    slug = "training_sessions"
    section_name = "training sessions"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of State"),
            DataTablesColumn("Name of District"),
            DataTablesColumn("Type of Training"),
            DataTablesColumn("Private: Number of Trainings"),
            DataTablesColumn("Private: Ayush trained"),
            DataTablesColumn("Private: Allopathics trained"),
            DataTablesColumn("Private: Learning change"),
            DataTablesColumn("Private: Num > 80%"),
            DataTablesColumn("Public: Number of Trainings"),
            DataTablesColumn("Public: Ayush trained"),
            DataTablesColumn("Public: Allopathics trained"),
            DataTablesColumn("Public: Learning change"),
            DataTablesColumn("Public: Num > 80%"),
            DataTablesColumn("Depot: Number of Trainings"),
            #            DataTablesColumn("Depot: Personnel trained"),
            DataTablesColumn("Depot: Learning change"),
            DataTablesColumn("Depot: Num > 80%"),
            DataTablesColumn("FLW: Number of Trainings"),
            #            DataTablesColumn("FLW: Personnel trained"),
            DataTablesColumn("FLW: Learning change"),
            DataTablesColumn("FLW: Num > 80%"))

    @property
    def rows(self):
        hh_data = psi_training_sessions(self.domain, {}, place_id=self.request.GET.get('location_id', ""),
            startdate=self.datespan.startdate_param_utc, enddate=self.datespan.enddate_param_utc)
        for d in hh_data:
            yield [
                d.get("state"),
                d.get("district"),
                d.get("training_type"),
                d["private_hcp"].get("num_trained"),
                d["private_hcp"].get("num_ayush_trained"),
                d["private_hcp"].get("num_allopathics_trained"),
                d["private_hcp"].get("avg_difference"),
                d["private_hcp"].get("num_gt80"),
                d["public_hcp"].get("num_trained"),
                d["public_hcp"].get("num_ayush_trained"),
                d["public_hcp"].get("num_allopathics_trained"),
                d["public_hcp"].get("avg_difference"),
                d["public_hcp"].get("num_gt80"),
                d["depot_training"].get("num_trained"),
                d["depot_training"].get("avg_difference"),
                d["depot_training"].get("num_gt80"),
                d["flw_training"].get("num_trained"),
                d["flw_training"].get("avg_difference"),
                d["flw_training"].get("num_gt80"),
                ]

def place_tree(domain):
    fdis = []; base_type = ""
    place_data_types = {}
    place_data_items = {}
    for pt in ["village", "block", "district", "state"]:
        place_data_types[pt] = FixtureDataType.by_domain_tag(domain, pt).one()
        place_data_items[pt] = FixtureDataItem.by_data_type(domain, place_data_types[pt].get_id).all()

    pdis_by_id = {}
    for pt, items in place_data_items.iteritems():
        pdis_by_id.update(dict((pdi.fields['id'], pdi) for pdi in items))

    tree_root = []
    for item in place_data_items["state"]:
        item._children = []
        item._place = "state"
        tree_root.append(item)

    for item in place_data_items["district"]:
        item._children = []
        item._place = "district"
        if item.fields.get('state_id', None):
            parent = pdis_by_id[item.fields['state_id']]
            try:
                parent._children.append(item)
            except AttributeError:
                pass
            #                print "Error(District): %s -> %s(%s)" % (item.fields['id'], parent.fields['id'], parent.get_id)

    for item in place_data_items["block"]:
        item._children = []
        item._place = "block"
        if item.fields.get('district_id', None):
            parent = pdis_by_id[item.fields['district_id']]
            try:
                parent._children.append(item)
            except AttributeError:
                pass
            #                print "Error(Block): %s -> %s(%s)" % (item.fields['id'], parent.fields['id'], parent.get_id)

    for item in place_data_items["village"]:
        item._children = []
        item._place = "village"
        if item.fields.get('block_id', None):
            parent = pdis_by_id[item.fields['block_id']]
            try:
                parent._children.append(item)
            except AttributeError:
                pass
            #                print "Error(Village): %s -> %s(%s)" % (item.fields['id'], parent.fields['id'], parent.get_id)

    return tree_root

class PlaceField(ReportField):
    name = ugettext_noop("State/District/Block/Village")
    slug = "place"
    template = "reports/fields/location.html"
    is_cacheable = True

    def update_context(self):
        self.context.update(self._get_custom_context())

    @request_cache('placefieldcontext')
    def _get_custom_context(self):
        all_locs = place_tree(self.domain)
        def loc_to_json(loc):
            return {
                'name': loc.fields['name'],
                #                'type': loc.location_type,
                'uuid': "%s:%s" % (loc._place, loc.fields['name']),
                'children': [loc_to_json(child) for child in loc._children],
                }
        loc_json = [loc_to_json(root) for root in all_locs]

        return {
            'control_name': self.name,
            'control_slug': self.slug,
            'loc_id': self.request.GET.get('location_id'),
            'locations': json.dumps(loc_json)
        }
