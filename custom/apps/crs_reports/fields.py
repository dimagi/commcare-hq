from corehq.apps.reports.dont_use.fields import ReportSelectField
from corehq.apps.reports.filters.users import SelectCaseOwnerFilter
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.es import CaseES


def _get_blocks(domain):
    query = (CaseES('report_cases')
             .domain(domain)
             .case_type(['pregnant_mother', 'baby'])
             .size(0)
             .terms_facet('block.#value', 'block'))
    return query.run().facets.block.terms


class SelectBlockField(ReportSelectField):
    slug = "block"
    name = ugettext_noop("Name of the Block")
    cssId = "opened_closed"
    cssClasses = "span3"

    def update_params(self):
        blocks = _get_blocks(self.domain)
        block = self.request.GET.get(self.slug, '')

        self.selected = block
        self.options = [dict(val=block_item, text="%s" % block_item) for block_item in blocks]
        self.default_option = _("Select Block")


class SelectSubCenterField(ReportSelectField):
    slug = "sub_center"
    name = ugettext_noop("Sub Center")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "Select Sub Center"
    options = []


class SelectASHAField(SelectCaseOwnerFilter):
    name = ugettext_noop("ASHA")
    default_option = ugettext_noop("Type ASHA name")
