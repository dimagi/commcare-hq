from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.letters.filters import GroupByFilter, SortByFilter, TemplatePropertyFilter
from corehq.apps.letters.models import LetterTemplate
from corehq.apps.letters.rendering import build_sections
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.standard import ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListMixin
from corehq.form_processor.models import CommCareCase

MAX_LETTERS = 500


@location_safe
class LetterReport(CaseListMixin, ProjectReport):
    """
    Renders one letter per filtered case from the LetterTemplate whose id is
    stored in a chosen case property. Non-tabular; printed via the browser.
    """
    name = gettext_lazy('Letters')
    slug = 'letters'
    description = gettext_lazy('Generate printable letters from cases and letter templates.')
    use_bootstrap5 = True
    printable = True
    exportable = False
    emailable = False
    toggles = (toggles.LETTER_TEMPLATES,)
    report_template_path = 'letters/letter_report.html'

    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
        'corehq.apps.letters.filters.TemplatePropertyFilter',
        'corehq.apps.letters.filters.GroupByFilter',
        'corehq.apps.letters.filters.SortByFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader()

    def get_sorting_block(self):
        return []  # ordering is done in build_sections

    def _base_query(self):
        return self.search_class().domain(self.domain).size(MAX_LETTERS + 1)

    @property
    def report_context(self):
        template_prop = TemplatePropertyFilter.get_value(self.request, self.domain)
        if not self.case_type or not template_prop:
            return {'needs_filters': True}
        case_ids = self._build_query().get_ids()
        if len(case_ids) > MAX_LETTERS:
            return {'too_many': MAX_LETTERS}
        cases = CommCareCase.objects.get_cases(case_ids, self.domain)
        # ponytail: loads every template body in the domain; filter by referenced ids if domains get many
        templates = {
            str(pk): body
            for pk, body in LetterTemplate.objects.filter(domain=self.domain).values_list('pk', 'body')
        }
        sections, skipped = build_sections(
            cases,
            templates,
            template_prop,
            group_by=GroupByFilter.get_value(self.request, self.domain),
            sort_by=SortByFilter.get_value(self.request, self.domain),
        )
        return {'sections': sections, 'skipped': skipped}
