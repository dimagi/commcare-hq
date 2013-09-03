from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from corehq.apps.reports.standard.inspect import GenericMapReport
from django.utils.translation import ugettext_noop
from corehq.apps.commtrack.models import Product

class StockStatusMapReport(GenericMapReport, CommtrackReportMixin):
    name = ugettext_noop("Stock Status (map)")
    slug = "stockstatus_map"

    fields = ['corehq.apps.reports.fields.AsyncLocationField']

    data_source = {
        'adapter': 'report',
        'geo_column': 'geo',
        'report': 'corehq.apps.reports.commtrack.data_sources.StockStatusBySupplyPointDataSource',
    }

    @property
    def display_config(self):
        conf = {
            'name_column': 'name',
            'detail_columns': ['type'],
            'column_titles': {
                'type': 'Supply Point Type',
            },
            'enum_captions': {},
            'numeric_format': {},
            'metrics': [
                {
                    'color': {
                        'column': 'type',
                    },
                },
            ],
        }

        titles = {
            'current_stock': 'Stock on Hand',
            'consumption': 'Monthly Consumption',
            'months_remaining': 'Months of Stock Remaining',
            'category': 'Current Stock Status',
        }

        products = sorted(Product.view('commtrack/products', startkey=[self.domain], endkey=[self.domain, {}], include_docs=True),
                          key=lambda p: p.name)
        for p in products:
            col_id = lambda c: '%s-%s' % (p._id, c)

            for c in ('category', 'current_stock', 'months_remaining', 'consumption'):
                conf['column_titles'][col_id(c)] = '%s: %s' % (p.name, titles[c])
                conf['detail_columns'].append(col_id(c))

            conf['metrics'].append({
                    'icon': {
                        'column': col_id('category'),
                        'categories': {
                            'stockout': '/static/commtrack/img/stockout.png',
                            'understock': '/static/commtrack/img/warning.png',
                            'adequate': '/static/commtrack/img/goodstock.png',
                            'overstock': '/static/commtrack/img/overstock.png',
                            #'nodata': '/static/commtrack/img/no_data.png',
                            '_null': '/static/commtrack/img/no_data.png',
                        },
                    }
                })
            conf['enum_captions'][col_id('category')] = {
                'stockout': 'Stocked out',
                'understock': 'Under-stock',
                'adequate': 'Adequate Stock',
                'overstock': 'Over-stock',
                '_null': 'No Data',
            }

            for c in ('current_stock', 'months_remaining', 'consumption'):
                metric = {
                    'title': conf['column_titles'][col_id(c)],
                    'size': {
                        'column': col_id(c),
                    },
                }
                if c not in ('consumption',):
                    metric['color'] = {
                        'column': col_id('category'),
                        'categories': {
                            'stockout': 'rgba(255, 0, 0, .8)',
                            'understock': 'rgba(255, 120, 0, .8)',
                            'adequate': 'rgba(50, 200, 50, .8)',
                            'overstock': 'rgba(120, 0, 255, .8)',
                            '_null': 'rgba(128, 128, 128, .8)',
                        },
                    }
                else:
                    metric['color'] = 'rgba(120, 120, 255, .8)'
                conf['metrics'].append(metric)

                conf['numeric_format'][col_id(c)] = {
                    'current_stock': "return x + ' %s'" % (p.unit or 'unit'),
                    'months_remaining': "return x + (x == 1 ? ' month' : ' months')",
                    'consumption': "return x + ' %s / month'" % (p.unit or 'unit'),
                }[c]

        return conf
