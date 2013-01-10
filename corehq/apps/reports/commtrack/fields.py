from corehq.apps.reports.fields import ReportMultiSelectField
from corehq.apps.commtrack.models import *
from corehq.apps.commtrack.util import *

class SupplyPointTypeField(ReportMultiSelectField):
    slug = 'outlet_type'
    name = 'Outlet Type'
    default_option = ['_all']

    @property
    def options(self):
        categories = supply_point_type_categories(self.domain)

        def indent(type):
            return (type, u'\u2013 %s' % type)

        choices = []
        choices.append(('_all', 'All Outlet Types'))
        for k, v in sorted(categories.items()):
            if k.startswith('_'):
                continue
            choices.append(('cat:%s' % k, k))
            for t in sorted(v):
                choices.append(indent(t))
        choices.append(('_oth', 'Other'))
        for t in sorted(categories['_oth']):
            choices.append(indent(t))
        return [{'val': e[0], 'text': e[1]} for e in choices]

class ProductField(ReportMultiSelectField):
    slug = 'product'
    name = 'Product'
    default_option = ['_all']

    @property
    def options(self):
        choices = [{'text': e[0], 'val': e[1]} for e in sorted((p.name, p._id) for p in Product.by_domain(self.domain))]
        choices.insert(0, {'text': 'All Products', 'val': '_all'})
        return choices
