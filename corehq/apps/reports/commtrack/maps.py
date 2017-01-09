from django.utils.translation import ugettext_noop
from corehq.apps.products.models import Product
from django.template.loader import render_to_string
from corehq.apps.reports.commtrack.standard import CommtrackReportMixin
from corehq.apps.reports.standard.maps import GenericMapReport
from corehq.apps.style.decorators import use_maps


class StockStatusMapReport(GenericMapReport, CommtrackReportMixin):
    name = ugettext_noop("Stock Status (map)")
    slug = "stockstatus_map"

    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.commtrack.ProgramFilter',
    ]

    data_source = {
        'adapter': 'report',
        'geo_column': 'geo',
        'report': 'corehq.apps.reports.commtrack.data_sources.StockStatusBySupplyPointDataSource',
    }

    @use_maps
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(StockStatusMapReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def display_config(self):
        conf = {
            'name_column': 'name',
            'detail_columns': ['type'],
            'table_columns': ['type'],
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

        products = sorted(
            Product.by_domain(self.domain),
            key=lambda p: p.name
        )

        if self.program_id:
            products = filter(lambda c: c.program_id == self.program_id, products)
        for p in products:
            col_id = lambda c: '%s-%s' % (p._id, c)

            product_cols = []
            for c in ('category', 'current_stock', 'months_remaining', 'consumption'):
                conf['column_titles'][col_id(c)] = titles[c]
                product_cols.append(col_id(c))
            conf['detail_columns'].extend(product_cols)

            product_metrics = [
                {
                    'icon': {
                        'column': col_id('category'),
                        'categories': {
                            'stockout': '/static/commtrack/images/stockout.png',
                            'understock': '/static/commtrack/images/warning.png',
                            'adequate': '/static/commtrack/images/goodstock.png',
                            'overstock': '/static/commtrack/images/overstock.png',
                            '_null': '/static/commtrack/images/no_data.png',
                        },
                    }
                }
            ]
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
                product_metrics.append(metric)

                conf['numeric_format'][col_id(c)] = {
                    'current_stock': "return x + ' %s'" % (p.unit or 'unit'),
                    'months_remaining': "return (Math.round(10 * x) / 10) + (x == 1 ? ' month' : ' months')",
                    'consumption': "return (Math.round(10 * x) / 10) + ' %s / month'" % (p.unit or 'unit'),
                }[c]

            conf['metrics'].append({
                'title': p.name,
                'group': True,
                'children': product_metrics,
            })
            conf['table_columns'].append({
                'title': p.name,
                'subcolumns': product_cols,
            })

        conf['detail_template'] = render_to_string('reports/partials/commtrack/stockstatus_mapdetail.html', {
            'products': products,
            'columns': [{'id': c, 'title': titles[c]} for c in
                        ('category', 'current_stock', 'consumption', 'months_remaining')],
        })

        conf['display'] = {
            'table': False,
        }
        return conf


class ReportingStatusMapReport(GenericMapReport, CommtrackReportMixin):
    name = ugettext_noop("Reporting Status (map)")
    slug = "reportingstatus_map"

    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.commtrack.ProgramFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

    data_source = {
        'adapter': 'report',
        'geo_column': 'geo',
        'report': 'corehq.apps.reports.commtrack.data_sources.ReportingStatusDataSource',
    }

    display_config = {
        'name_column': 'name',
        'detail_columns': ['type', 'reporting_status'],
        'column_titles': {
            'type': 'Supply Point Type',
            'reporting_status': 'Current Reporting Status',
        },
        'enum_captions': {
            'reporting_status': {
                'reporting': 'Reporting',
                'nonreporting': 'Non-reporting',
            },
        },
        'metrics': [
            {
                'color': {
                    'column': 'type',
                },
            },
            {
                'default': True,
                'color': {
                    'column': 'reporting_status',
                    'categories': {
                        'reporting': 'rgba(0, 200, 0, .8)',
                        'nonreporting': 'rgba(255, 0, 0, .8)',
                    },
                },
            },
        ],
    }

    @use_maps
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ReportingStatusMapReport, self).decorator_dispatcher(request, *args, **kwargs)
