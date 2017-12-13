from __future__ import absolute_import
from copy import copy
import logging
from corehq.util.dates import iso_string_to_date
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from django.utils.html import format_html
from django.utils.translation import ugettext_noop, ugettext as _
from custom.bihar.reports.indicators.reports import ClientListBase
from custom.bihar.reports.supervisor import (SubCenterSelectionReport, BiharNavReport, GroupReferenceMixIn,
                                      shared_bihar_context, team_member_context, BiharSummaryReport,
                                      url_and_params)
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.generic import summary_context
from corehq.apps.api.es import ReportCaseES
from datetime import datetime, timedelta, time
from dimagi.utils.parsing import json_format_date

BIHAR_DOMAIN = 'care-bihar' # TODO: where should this go?
BIHAR_CHILD_CASE_TYPE = 'cc_bihar_newborn'
MAX_ES_RESULTS = 1000000

DUE_LIST_CONFIG = [
    {
        'slug': 'anc',
        'title': ugettext_noop('ANC'),
        'tasks': [
            "anc_1",
            "anc_2",
            "anc_3",
            "anc_4",
            ]
    },
    {
        'slug': 'tt',
        'title': ugettext_noop('TT'),
        'tasks': [
            "tt_1",
            "tt_2",
            "tt_booster",
            ]
    },
    {
        'slug': 'bcg',
        'title': ugettext_noop('BCG'),
        'tasks': ["bcg",]
    },
    {
        'slug': 'opv',
        'title': ugettext_noop('OPV'),
        'tasks': [
            "opv_0",
            "opv_1",
            "opv_2",
            "opv_3",
            "opv_booster",
            ]
    },
    {
        'slug': 'dpt',
        'title': ugettext_noop('DPT'),
        'tasks': ["dpt_1",
                  "dpt_2",
                  "dpt_3",
                  "dpt_booster",
                  ]
    },
    {
        'slug': 'hepb',
        'title': ugettext_noop('Hepatitis B'),
        'tasks': ["hep_0",
                  "hep_1",
                  "hep_2",
                  "hep_3",
                  ]
    },
    {
        'slug': 'measles',
        'title': ugettext_noop('Measles'),
        'tasks': ["measles",]
    },
    {
        'slug': 'vita',
        'title': ugettext_noop('Vitamin A'),
        'tasks': ["vita_1",]
    },
    # test - to ignore: ["hep_b_0", "je", "vit_a_1"]
]


def get_config_item_by_slug(slug):
    for i in DUE_LIST_CONFIG:
        if i['slug'] == slug:
            return i


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
        return [_("Vaccination Name")] + [_(res[0]['title']) for res in self.due_list_results()]

    @property
    def data(self):
        def _fmt_result(item_config, value):
            params = copy(self.request_params)
            params['category'] = item_config['slug']
            params['date'] = json_format_date(self.get_date())
            return format_html(u'<a href="{next}">{val}</a>',
                val=value,
                next=url_and_params(
                    VaccinationClientList.get_url(self.domain,
                                                  render_as=self.render_next),
                    params
            ))
        return [_("# Due")] + [_fmt_result(*res) for res in self.due_list_results()]

    @memoized
    def due_list_results(self):
        """
        Returns the due list in a list of tuples of the form (type, count)
        """
        target_date = self.get_date()
        owner_id = self.group_id
        by_task_name = get_due_list_by_task_name(target_date, owner_id)
        return list(format_results(by_task_name))


class VaccinationClientList(ClientListBase):
    name = ugettext_noop("Vaccination Client List")
    slug = "vacdetails"
    description = "Vaccination client list report"

    @property
    def _headers(self):
        return [_('Mother'), _('Husband'), _('Child')]

    @property
    @memoized
    def config_item(self):
        return get_config_item_by_slug(self.request_params.get('category'))

    @memoized
    def get_date(self):
        return datetime.combine(
            iso_string_to_date(self.request_params.get('date')),
            time()
        )

    @property
    def rendered_report_title(self):
        return u'{title} ({count})'.format(title=_(self.config_item['title']), count=len(self.rows)) \
            if self.config_item else super(VaccinationClientList, self).rendered_report_title

    @property
    @memoized
    def rows(self):
        target_date = self.get_date()
        owner_id = self.group_id
        if not self.config_item:
            return

        def _related_id(res):
            try:
                [index] = res['indices']
                return index['referenced_id']
            except Exception:
                logging.exception('problem loading related case from task %s' % res['_id'])
                return None

        def _get_related_cases(results):
            ids = [_f for _f in [_related_id(res) for res in results] if _f]
            return dict((c['_id'], c) for c in iter_docs(CommCareCase.get_db(), ids))

        results = get_due_list_records(target_date, owner_id=owner_id, task_types=self.config_item['tasks'])
        # this preloads the cases we'll need into memory to avoid excessive couch
        # queries to get related cases
        primary_cases = _get_related_cases(results)
        secondary_cases = _get_related_cases([x for x in primary_cases.values() if x['type'] == BIHAR_CHILD_CASE_TYPE])

        def _to_row(case):
            # this function uses closures so don't move it!
            if case['type'] == BIHAR_CHILD_CASE_TYPE:
                mom = secondary_cases.get(_related_id(case))
                if mom:
                    return [mom['name'], mom['husband_name'], case['name']]
                else:
                    return ['?', '?', case['name']]
            else:
                return [case['name'], case['husband_name'], '?']

        return [_to_row(case) for case in primary_cases.values()]


def format_results(results):
    results_dict = dict(results)
    for item in DUE_LIST_CONFIG:
        yield (item, sum(results_dict.get(t, 0) for t in item['tasks']))


def get_due_list_by_task_name(target_date, owner_id=None, case_es=None, size=0, case_type='task'):
    case_es = case_es or ReportCaseES(BIHAR_DOMAIN)
    es_type=None
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
            {"range": {"date_eligible.#value": {"to": json_format_date(target_date)}}},
            {"range": {"date_expires.#value": {"from": json_format_date(target_date)}}},
        ]
    }

    base_query['filter']['and'] += filter['and']
    base_query['facets'] = {
        facet_name: {
            "terms": {"field":"task_id.#value", "size": 1000},
            "facet_filter": filter # This controls the records processed for the summation
        }
    }
    es_result = case_es.run_query(base_query, es_type=es_type)
    return ((facet['term'], facet['count']) for facet in es_result['facets'][facet_name]['terms'])


def get_due_list_records(target_date, owner_id=None, task_types=None, case_es=None, size=MAX_ES_RESULTS, case_type='task'):
    '''
    A drill-down of the get_due_list_by_task_name, this returns the records for a particular
    set of types (which is the type of vaccination)
    '''
    case_es = case_es or ReportCaseES(BIHAR_DOMAIN)
    es_type = None

    # The type of vaccination is stored in the `name` field in ElasticSearch
    # so we filter on `name.exact` so that "OPV 1" is not tokenized into two words

    base_query = case_es.base_query(start=0, size=size)

    owner_filter = {"match_all":{}} if owner_id is None else {"term": {"owner_id": owner_id}}

    name_filter = {"match_all":{}} if not task_types else {"terms": {"task_id.#value": task_types}}
    filter = {
        "and": [
            owner_filter,
            name_filter,
            {"term": {"closed": False}},
            {"term": {"type": case_type}},
            {"range": {"date_eligible.#value": {"to": target_date.isoformat() }}},
            {"range": {"date_expires.#value": {"from": target_date.isoformat()}}},
        ]
    }

    base_query['filter']['and'] += filter['and']
    es_result = case_es.run_query(base_query, es_type=es_type)
    return (result['_source'] for result in es_result['hits']['hits'])

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
