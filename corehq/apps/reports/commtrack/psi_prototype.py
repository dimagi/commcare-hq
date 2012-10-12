from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.domain.models import Domain
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from dimagi.utils.couch.database import get_db

class CommtrackReportMixin(ProjectReport, ProjectReportParametersMixin):
    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        domain = Domain.get_by_name(kwargs['domain'])
        return domain.commtrack_enabled
    
class VisitReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Visit Report'
    slug = 'visits'
    fields = []

    @property
    def products(self):
        query = get_db().view('commtrack/products', start_key=[self.domain], end_key=[self.domain, {}], include_docs=True)
        prods = [e['doc'] for e in query]
        return sorted(prods, key=lambda p: p['name'])

    @property
    def actions(self):
        from corehq.apps.commtrack.sms import report_syntax_config as config
        return sorted(config['single_action']['keywords'].keys())

    @property
    def headers(self):
        cols = [
            DataTablesColumn('Outlet'),
            # TODO lots of static outlet info
            DataTablesColumn('Date'),
            #DataTablesColumn('Reporter'),
        ]
        for a in self.actions:
            for p in self.products:
                cols.append(DataTablesColumn('%s (%s)' % (a, p['name'])))
        
        return DataTablesHeader(*cols)

    @property
    def rows(self):
        products = self.products
        actions = self.actions

        reports = get_db().view('commtrack/stock_reports',
                                start_key=[self.domain, '2012-10-12T23:08:30Z'], # DEBUG time filter to hide incompatible instances
                                end_key=[self.domain, {}],
                                include_docs=True)

        def row(doc):
            from collections import Sequence
            txs = doc['form']['transaction']
            if not isinstance(txs, Sequence):
                txs = [txs]
            transactions = dict(((tx['action'], tx['product']), tx['value']) for tx in txs)

            data = [
                doc['form'].get('location'),
                doc['received_on'],
            ]
            for a in actions:
                for p in products:
                    data.append(transactions.get((a, p['_id']), ''))

            return data

        return [row(e['doc']) for e in reports]

class SalesAndConsumptionReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Sales and Consumption Report'
    slug = 'sales_consumption'

