from corehq.apps.reports.fields import ReportMultiSelectField
from corehq.apps.commtrack.models import *
from corehq.apps.commtrack.util import *

class SupplyPointTypeField(ReportMultiSelectField):
    slug = 'outlet_type'
    name = 'Outlet Type'
    multiple = True

    @property
    def options(self):
        config = CommtrackConfig.for_domain(self.domain)
        categories = config.supply_point_categories
        choices = [('_all', 'All Outlet Types')]
        for k, v in sorted(categories.items()):
            choices.append(('cat:%s' % k, k))
            for t in sorted(v):
                choices.append((t, u'\u2013 %s' % t))
        choices.append(('_oth', 'Other'))
        for t in sorted(set(all_supply_point_types(self.domain)) - set(config.known_supply_point_types)):
            choices.append((t, u'\u2013 %s' % t))
        return [{'val': e[0], 'text': e[1]} for e in choices]
