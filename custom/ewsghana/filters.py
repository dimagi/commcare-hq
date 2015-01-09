from django.utils.translation import ugettext_noop
from corehq.apps.products.models import Product
from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter


class ProductByProgramFilter(BaseDrilldownOptionFilter):
    slug = "filter_by"
    single_option_select = 0
    template = "opm/drilldown_options.html"
    label = ugettext_noop("Filter By")

    @property
    def drilldown_map(self):
        options = [{"val": "0", "text": "All", "next": []}]
        for program in Program.by_domain(self.domain):
            products = [{"val": "0", "text": "All", "next": []}]
            for product in Product.by_program_id(self.domain, program._id):
                products.append({"val": product.get_id, "text": product.name})
            options.append({"val": program.get_id, "text": program.name, "next": products})
        return options

    @classmethod
    def get_labels(cls):
        return [('Program', 'program'), ('Product', 'product')]

    @property
    def filter_context(self):
        controls = []
        for level, label in enumerate(self.rendered_labels):
            controls.append({
                'label': label[0],
                'slug': label[1],
                'level': level,
            })

        return {
            'option_map': self.drilldown_map,
            'controls': controls,
            'selected': self.selected,
            'use_last': self.use_only_last,
            'notifications': self.final_notifications,
            'empty_text': self.drilldown_empty_text,
            'is_empty': not self.drilldown_map,
            'single_option_select': self.single_option_select
        }

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[1])))
        return {
            'slug': slug,
            'value': val,
        }


class ViewReportFilter(BaseSingleOptionFilter):
    default_text = ugettext_noop("All Stock Information")
    slug = 'report_type'
    label = 'View'

    @property
    def options(self):
        return [
            ('stockouts', 'Stockouts'),
            ('pa', 'Product Availability')
        ]
