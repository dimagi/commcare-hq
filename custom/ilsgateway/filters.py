from django.utils.translation import ugettext_noop
from corehq.apps.products.models import Product
from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter


class ProductByProgramFilter(BaseDrilldownOptionFilter):
    slug = "filter_by"
    label = ugettext_noop("Filter By")

    @property
    def drilldown_map(self):
        options = []
        for program in Program.by_domain(self.domain):
            products = []
            for product in Product.by_program_id(self.domain, program._id):
                products.append({"val": product.get_id, "text": product.name})
            options.append({"val": program.get_id, "text": program.name, "next": products})
        return options

    @classmethod
    def get_labels(cls):
        return [('Program', 'All', 'program'), ('Product', 'All', 'product')]


class MSDZoneFilter(BaseSingleOptionFilter):

    slug = 'msd'
    label = 'MSD zone'

    @property
    def options(self):
        return [
            ('MT', 'Mtwara'),
            ('MS', 'Moshi'),
            ('MB', 'Mbeya'),
            ('TB', 'Tabora'),
            ('MW', 'Mwanza'),
            ('IR', 'Iringa'),
            ('DR', 'Dar'),
            ('DM', 'Dodoma'),
            ('TG', 'Tanga'),
        ]