from datetime import datetime
import logging

from django.core.urlresolvers import reverse
from django.utils import html
from django.utils.translation import ugettext as _, ugettext_noop
import simplejson

from corehq.apps.api.es import ReportCaseES
from corehq.apps.cloudcare.api import get_cloudcare_app, get_cloudcare_form_url
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.elastic import es_query
from corehq.pillows.base import restore_property_dict
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from custom.succeed import PatientInfoReport
from custom.succeed.reports import VISIT_SCHEDULE, LAST_INTERACTION_LIST, EMPTY_FIELD, \
    INPUT_DATE_FORMAT, OUTPUT_DATE_FORMAT, CM_APP_UPDATE_VIEW_TASK_MODULE, CM_UPDATE_TASK, TASK_RISK_FACTOR
from custom.succeed.utils import is_succeed_admin, has_any_role, SUCCEED_CM_APPNAME, get_app_build
from casexml.apps.case.models import CommCareCase
from dimagi.utils.decorators.memoized import memoized


class PatientTaskListReportDisplay(CaseDisplay):
    def __init__(self, report, case_dict):

        next_visit = VISIT_SCHEDULE[0]
        last_inter = None
        for action in case_dict['actions']:
            if action['xform_xmlns'] in LAST_INTERACTION_LIST:
                last_inter = action

        for visit_key, visit in enumerate(VISIT_SCHEDULE):
            for key, action in enumerate(case_dict['actions']):
                if visit['xmlns'] == action['xform_xmlns']:
                    try:
                        next_visit = VISIT_SCHEDULE[visit_key + 1]
                        del case_dict['actions'][key]
                        break
                    except IndexError:
                        next_visit = 'last'
        self.next_visit = next_visit
        if last_inter:
            self.last_interaction = last_inter['date']
        self.domain = report.domain
        self.app_dict = get_cloudcare_app(self.domain, SUCCEED_CM_APPNAME)
        self.latest_build = get_app_build(self.app_dict)
        super(PatientTaskListReportDisplay, self).__init__(report, case_dict)

    def get_property(self, key):
        if key in self.case:
            return self.case[key]
        else:
            return EMPTY_FIELD

    def get_link(self, url, field):
        if url:
            return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (url, html.escape(field)))
        else:
            return "%s (bad ID format)" % self.case["indices"][0]["referenced_id"]

    def get_form_url(self, app_dict, app_build_id, module_idx, form, case_id=None):
        try:
            module = app_dict['modules'][module_idx]
            form_idx = [ix for (ix, f) in enumerate(module['forms']) if f['xmlns'] == form][0]
        except IndexError:
            form_idx = None

        return html.escape(get_cloudcare_form_url(domain=self.domain,
                                                  app_build_id=app_build_id,
                                                  module_id=module_idx,
                                                  form_id=form_idx,
                                                  case_id=case_id) + '/enter/')

    @property
    @memoized
    def full_name(self):
        return CommCareCase.get(self.get_property("indices")[0]["referenced_id"])["full_name"]

    @property
    def full_name_url(self):
        return html.escape(
                PatientInfoReport.get_url(*[self.case["domain"]]) + "?patient_id=%s" % self.case["indices"][0]["referenced_id"])

    @property
    def full_name_link(self):
        return self.get_link(self.full_name_url, self.full_name)

    @property
    def name(self):
        return self.get_property("name")

    @property
    def name_url(self):
        if self.status == "Closed":
            url = reverse('case_details', args=[self.domain, self.get_property("_id")])
            return url + '#!history'
        else:
            return self.get_form_url(self.app_dict, self.latest_build, CM_APP_UPDATE_VIEW_TASK_MODULE, CM_UPDATE_TASK, self.get_property("_id"))


    @property
    def name_link(self):
        return self.get_link(self.name_url, self.name)

    @property
    def task_responsible(self):
        return self.get_property("task_responsible")

    @property
    def case_filter(self):
        filters = []
        care_site = self.request_params.get('task_responsible', '')
        if care_site != '':
            filters.append({'term': {'task_responsible.#value': care_site.lower()}})
        return {'and': filters} if filters else {}

    @property
    def status(self):
        return self.get_property("closed") and "Closed" or "Open"

    @property
    def task_due(self):
        rand_date = self.get_property("task_due")
        if rand_date != EMPTY_FIELD:
            date = datetime.strptime(rand_date, INPUT_DATE_FORMAT)
            return date.strftime(OUTPUT_DATE_FORMAT)
        else:
            return EMPTY_FIELD

    @property
    def last_modified(self):
        rand_date = self.get_property("last_updated")
        if rand_date != EMPTY_FIELD:
            date = datetime.strptime(rand_date, INPUT_DATE_FORMAT)
            return date.strftime(OUTPUT_DATE_FORMAT)
        else:
            return EMPTY_FIELD

    @property
    def task_type(self):
        return self.get_property("task_type")

    @property
    def task_risk_factor(self):
        return TASK_RISK_FACTOR[self.get_property("task_risk_factor")]

    @property
    def task_details(self):
        return self.get_property("task_details")


class PatientTaskListReport(CustomProjectReport, ElasticProjectInspectionReport, ProjectReportParametersMixin):
    ajax_pagination = True
    name = ugettext_noop('Patient Tasks')
    slug = 'patient_task_list'
    default_sort = {'task_due.#value': 'asc'}
    base_template_filters = 'succeed/report.html'
    case_type = 'task'

    fields = ['custom.succeed.fields.ResponsibleParty',
              'custom.succeed.fields.PatientName',
              'custom.succeed.fields.TaskStatus',
              'corehq.apps.reports.standard.cases.filters.CaseSearchFilter']

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if domain and project and user is None:
            return True
        if user and (is_succeed_admin(user) or has_any_role(user)):
            return True
        return False

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    @memoized
    def case_es(self):
        return ReportCaseES(self.domain)

    @property
    def case_filter(self):
        filters = []
        care_site = self.request_params.get('care_site', '')
        if care_site != '':
            filters.append({'term': {'care_site.#value': care_site.lower()}})
        return {'and': filters} if filters else {}

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Patient Name")),
            DataTablesColumn(_("Task Name"), prop_name="name"),
            DataTablesColumn(_("Responsible Party"), prop_name="task_responsible", sortable=False),
            DataTablesColumn(_("Status"), prop_name='status', sortable=False),
            DataTablesColumn(_("Action Due"), prop_name="task_due.#value"),
            DataTablesColumn(_("Last Update"), prop_name='last_updated.#value'),
            DataTablesColumn(_("Task Type"), prop_name="task_type"),
            DataTablesColumn(_("Associated Risk Factor"), prop_name="task_risk_factor.#value"),
            DataTablesColumn(_("Details"), prop_name="task_details", sortable=False),
        )
        return headers

    def get_visit_script(self, order, responsible_party):
        return {
            "script":
                """
                    next_visit=visits_list[0];
                    before_action=null;
                    count=0;
                    foreach(visit : visits_list) {
                        skip = false;
                        foreach(action : _source.actions) {
                            if (!skip && visit.xmlns.equals(action.xform_xmlns) && !action.xform_id.equals(before_action)) {
                                next_visit=visits_list[count+1];
                                before_visit=action.xform_id;
                                skip=true;
                                count++;
                            }
                            before_visit=action.xform_id;
                        }
                    }
                    return next_visit.get('responsible_party').equals(responsible_party);
                """,
            "params": {
                "visits_list": VISIT_SCHEDULE,
                "responsible_party": responsible_party
            }
        }

    @property
    @memoized
    def es_results(self):
        q = { "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "and": [
                            {"term": { "domain.exact": "succeed" }},
                        ]
                    }
                }
            },
            'sort': self.get_sorting_block(),
            'from': self.pagination.start if self.pagination else None,
            'size': self.pagination.count if self.pagination else None,
        }
        search_string = SearchFilter.get_value(self.request, self.domain)
        es_filters = q["query"]["filtered"]["filter"]

        responsible_party = self.request_params.get('responsible_party', '')
        if responsible_party != '':
            if responsible_party == 'Care Manager':
                es_filters["and"].append({"term": {"task_responsible.#value": "cm"}})
            else:
                es_filters["and"].append({"term": {"task_responsible.#value": "chw"}})


        task_status = self.request_params.get('task_status', '')
        if task_status != '':
            if task_status == 'closed':
                es_filters["and"].append({"term": {"closed": True}})
            else:
                es_filters["and"].append({"term": {"closed": False}})

        patient_id = self.request_params.get('patient_id', '')
        if patient_id != '':
            es_filters["and"].append({"term": {"indices.referenced_id": patient_id}})

        def _filter_gen(key, flist):
            return {"terms": {
                key: [item.lower() for item in flist if item]
            }}

        user = self.request.couch_user
        if not user.is_web_user():
            owner_ids = user.get_group_ids()
            user_ids = [user._id]
            owner_filters = _filter_gen('owner_id', owner_ids)
            user_filters = _filter_gen('user_id', user_ids)
            filters = filter(None, [owner_filters, user_filters])
            subterms = []
            subterms.append({'or': filters})
            es_filters["and"].append({'and': subterms} if subterms else {})

        if self.case_type:
            es_filters["and"].append({"term": {"type.exact": 'task'}})
        if search_string:
            query_block = {"queryString": {"query": "*" + search_string + "*"}}
            q["query"]["filtered"]["query"] = query_block

        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(q)))

        if self.pagination:
            return es_query(q=q, es_url=REPORT_CASE_INDEX + '/_search', dict_only=False, start_at=self.pagination.start)
        else:
            return es_query(q=q, es_url=REPORT_CASE_INDEX + '/_search', dict_only=False)

    @property
    def get_all_rows(self):
        return self.rows

    @property
    def rows(self):
        case_displays = (PatientTaskListReportDisplay(self, restore_property_dict(self.get_case(case)))
                         for case in self.es_results['hits'].get('hits', []))

        if self.request_params["iSortCol_0"] == 0:
            if self.request_params["sSortDir_0"] == "asc":
                case_displays = sorted(case_displays, key=lambda x: x.full_name)
            else:
                case_displays = sorted(case_displays, key=lambda x: x.full_name, reverse=True)

        for disp in case_displays:
            yield [
                disp.full_name_link,
                disp.name_link,
                disp.task_responsible,
                disp.status,
                disp.task_due,
                disp.last_modified,
                disp.task_type,
                disp.task_risk_factor,
                disp.task_details
            ]

    @property
    def user_filter(self):
        return super(PatientTaskListReport, self).user_filter

    def get_case(self, row):
        if '_source' in row:
            case_dict = row['_source']
        else:
            raise ValueError("Case object is not in search result %s" % row)

        if case_dict['domain'] != self.domain:
            raise Exception("case.domain != self.domain; %r and %r, respectively" % (case_dict['domain'], self.domain))

        return case_dict