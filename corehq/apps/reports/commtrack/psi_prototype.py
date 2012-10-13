from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.domain.models import Domain
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.loosechange import map_reduce
import itertools

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
        from corehq.apps.commtrack.sms import report_syntax_config as config
        return sorted(config['single_action']['keywords'].keys())

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
                doc['received_on'],
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
            cols.append(DataTablesColumn('Stock on Hand (%s)' % p['name'])) # latest value + date of latest report
            cols.append(DataTablesColumn('Total Sales (%s)' % p['name']))
            cols.append(DataTablesColumn('Total Consumption (%s)' % p['name']))
        # total 'combined' stock-out days (ugh)

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
                    as_of = latest_state['server_date']

                data.append('%s (%s)' % (stock, as_of) if latest_state else '')
                data.append(sum(tx_by_action.get('receipts', [])))
                data.append(sum(tx_by_action.get('consumption', [])))

            return data

        return [summary_row(site, reports_by_loc.get(site, [])) for site in locs]
