from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.models import *
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.loosechange import map_reduce
import itertools
from datetime import datetime, date, timedelta

class CommtrackReportMixin(ProjectReport, ProjectReportParametersMixin):
    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        domain = Domain.get_by_name(kwargs['domain'])
        return domain.commtrack_enabled
    
    @property
    def products(self):
        query = get_db().view('commtrack/products', start_key=[self.domain], end_key=[self.domain, {}], include_docs=True)
        prods = [e['doc'] for e in query]
        return sorted(prods, key=lambda p: p['name'])

    @property
    def actions(self):
        return sorted(CommtrackConfig.for_domain(self.domain).actions.keys())

def get_transactions(form_doc):
    from collections import Sequence
    txs = form_doc['form']['transaction']
    if not isinstance(txs, Sequence):
        txs = [txs]
    return txs

def get_stock_reports(domain):
    query = get_db().view('commtrack/stock_reports',
                          start_key=[domain, '2012-10-12T23:08:30Z'], # DEBUG time filter to hide incompatible instances
                          end_key=[domain, {}],
                          include_docs=True)
    return [e['doc'] for e in query]

def parse_iso(dt):
    return datetime.strptime(dt, '%Y-%m-%dT%H:%M:%SZ')

class VisitReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Visit Report'
    slug = 'visits'
    fields = ['corehq.apps.reports.fields.FilterUsersField']

    @property
    def headers(self):
        cols = [
            DataTablesColumn('Outlet'),
            # TODO lots of static outlet info
            DataTablesColumn('Date'),
            #DataTablesColumn('Reporter'),
        ]
        for p in self.products:
            for a in self.actions:
                cols.append(DataTablesColumn('%s (%s)' % (a, p['name'])))
        
        return DataTablesHeader(*cols)

    @property
    def rows(self):
        products = self.products
        actions = self.actions
        reports = get_stock_reports(self.domain)

        def row(doc):
            transactions = dict(((tx['action'], tx['product']), tx['value']) for tx in get_transactions(doc))

            data = [
                doc['form']['location'],
                parse_iso(doc['received_on']).strftime('%Y-%m-%d'),
            ]
            for p in products:
                for a in actions:
                    data.append(transactions.get((a, p['_id']), ''))

            return data

        return [row(r) for r in reports]

class SalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Sales and Consumption Report'
    slug = 'sales_consumption'
    fields = ['corehq.apps.reports.fields.FilterUsersField']

    @property
    def headers(self):
        cols = [
            DataTablesColumn('Outlet'),
            # TODO lots of static outlet info
        ]
        for p in self.products:
            cols.append(DataTablesColumn('Stock on Hand (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Sales (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Consumption (%s)' % p['name']))
        cols.append(DataTablesColumn('Stock-out days (all products combined)'))

        return DataTablesHeader(*cols)

    @property
    def rows(self):
        products = self.products
        reports = get_stock_reports(self.domain)
        reports_by_loc = map_reduce(lambda e: [(e['form']['location'],)], data=reports, include_docs=True)

        locs = sorted(reports_by_loc.keys()) # todo: pull from location hierarchy

        def summary_row(site, reports):
            all_transactions = list(itertools.chain(*(get_transactions(r) for r in reports)))
            tx_by_product = map_reduce(lambda tx: [(tx['product'],)], data=all_transactions, include_docs=True)

            data = [
                site,
            ]
            stockouts = {}
            for p in products:
                tx_by_action = map_reduce(lambda tx: [(tx['action'], int(tx['value']))], data=tx_by_product.get(p['_id'], []))

                # TODO: add date filter
                start_key = [str(self.domain), site, p['_id']]
                end_key = list(itertools.chain(start_key, [{}]))
                # list() is necessary or else get a weird error
                product_states = list(get_db().view('commtrack/stock_product_state', start_key=start_key, end_key=end_key))
                latest_state = product_states[-1]['value'] if product_states else None
                if latest_state:
                    stock = latest_state['updated_unknown_properties']['current_stock']
                    as_of = parse_iso(latest_state['server_date']).strftime('%Y-%m-%d')

                stockout_dates = set()
                for state in product_states:
                    doc = state['value']
                    stocked_out_since = doc['updated_unknown_properties']['stocked_out_since']
                    if stocked_out_since:
                        so_start = datetime.strptime(stocked_out_since, '%Y-%m-%d').date() # todo: clip to start of time filter
                        so_end = parse_iso(doc['server_date']).date() # time zone issues
                        dt = so_start
                        while dt < so_end:
                            stockout_dates.add(dt)
                            dt += timedelta(days=1)
                stockouts[p['_id']] = stockout_dates

                data.append('%s (%s)' % (stock, as_of) if latest_state else '')
                data.append(sum(tx_by_action.get('receipts', [])))
                data.append(sum(tx_by_action.get('consumption', [])))

            combined_stockout_days = len(reduce(lambda a, b: a.intersection(b), stockouts.values()))
            data.append(combined_stockout_days)

            return data

        return [summary_row(site, reports_by_loc.get(site, [])) for site in locs]
