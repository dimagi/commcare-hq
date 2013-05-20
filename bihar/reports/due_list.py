from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_noop, ugettext as _
from bihar.reports.supervisor import SubCenterSelectionReport, BiharNavReport, GroupReferenceMixIn, shared_bihar_context, team_member_context, BiharSummaryReport
from corehq.apps.reports.generic import summary_context
from corehq.apps.api.es import FullCaseES
from datetime import datetime, timedelta

BIHAR_DOMAIN = 'care-bihar' # TODO: where should this go?

class DueListNav(GroupReferenceMixIn, BiharNavReport):
    slug = "duelistnav"
    name = ugettext_noop("Due List")
    description = ugettext_noop("Indicator navigation")
    preserve_url_params = True
    report_template_path = "bihar/team_listing_tabular.html"

    extra_context_providers = [shared_bihar_context, summary_context, team_member_context]
    @property
    def reports(self):
        return [VaccinationSummaryToday, VaccinationSummaryTomorrow,
                VaccinationSummary2Days, VaccinationSummary3Days]

    @property
    def rendered_report_title(self):
        return self.group_display

class VaccinationSummary(GroupReferenceMixIn, BiharSummaryReport):
    name = ugettext_noop("Care Due")
    slug = "vaccinationsummary"
    description = "Vaccination summary report"
    base_template_mobile = "bihar/bihar_summary.html"
    is_cacheable = True

    def get_date(self):
        # override
        raise NotImplemented()

    @property
    def _headers(self):
        return [_("Vaccination Name")] + [res[0] for res in self.due_list_by_task_name()]

    @property
    def data(self):
        return [_("# Due")] + [res[1] for res in self.due_list_by_task_name()]

    @memoized
    def due_list_by_task_name(self):
        """
        Returns the due list in a list of tuples of the form (type, count)
        """
        target_date = self.get_date()
        owner_id = self.group_id
        return sorted(get_due_list_by_task_name(target_date, owner_id),
                      key=lambda tup: tup[0])



def get_due_list_by_task_name(target_date, owner_id=None, case_es=None, size=0, case_type='task'):
    case_es = case_es or FullCaseES(BIHAR_DOMAIN)
    es_type = 'fullcase_%(domain)s__%(case_type)s' % { 'domain': BIHAR_DOMAIN, 'case_type': 'task' }
    facet_name = 'vaccination_names'

    # The type of vaccination is stored in the `name` field in ElasticSearch
    # so we can get the sums directly as facets on `name.exact` where the `.exact`
    # is to avoid tokenization so that "OPV 1" does not create two facets.

    base_query = case_es.base_query(start=0, size=size)

    owner_filter = {"match_all":{}} if owner_id is None else {"term": {"owner_id": owner_id}}

    filter = {
        "and": [
            owner_filter,
            {"term": {"closed": False}},
            {"term": {"type": case_type}},
            {"range": {"date_eligible": {"to": target_date.isoformat() }}},
            {"range": {"date_expires": {"from": target_date.isoformat()}}},
        ]
    }

    base_query['filter']['and'] += filter['and']
    base_query['facets'] = {
        facet_name: {
            "terms": {"field":"name.exact"},
            "facet_filter": filter # This controls the records processed for the summation
        }
    }
    es_result = case_es.run_query(base_query, es_type=es_type)
    return ((facet['term'], facet['count']) for facet in es_result['facets'][facet_name]['terms'])

# TODO: this is pretty silly but doing this without classes would be a bit of extra work
class VaccinationSummaryToday(VaccinationSummary):
    name = ugettext_noop("Care Due Today")
    slug = "vacstoday"
    def get_date(self):
        return datetime.today()

class VaccinationSummaryTomorrow(VaccinationSummary):
    name = ugettext_noop("Care Due Tomorrow")
    slug = "vacstomorrow"
    def get_date(self):
        return datetime.today() + timedelta(days=1)

class VaccinationSummaryTomorrow(VaccinationSummary):
    name = ugettext_noop("Care Due Tomorrow")
    slug = "vacstomorrow"
    def get_date(self):
        return datetime.today() + timedelta(days=1)

class VaccinationSummary2Days(VaccinationSummary):
    name = ugettext_noop("Care Due In 2 Days")
    slug = "vacs2days"
    def get_date(self):
        return datetime.today() + timedelta(days=2)

class VaccinationSummary3Days(VaccinationSummary):
    name = ugettext_noop("Care Due In 3 Days")
    slug = "vacs3days"
    def get_date(self):
        return datetime.today() + timedelta(days=3)


class DueListSelectionReport(SubCenterSelectionReport):
    slug = "duelistselect"
    name = ugettext_noop("Due List")

    next_report_slug = DueListNav.slug
    next_report_class = DueListNav


