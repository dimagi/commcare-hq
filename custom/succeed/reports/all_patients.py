from datetime import datetime, timedelta
from couchdbkit import ResourceNotFound
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.groups.models import Group
from custom.succeed.reports.patient_interactions import PatientInteractionsReport
from custom.succeed.reports.patient_task_list import PatientTaskListReport
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.api.es import ReportCaseES
from corehq.apps.cloudcare.api import get_cloudcare_app, get_cloudcare_form_url
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.elastic import es_query
from corehq.pillows.base import restore_property_dict
from django.utils import html
import dateutil
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from custom.succeed.reports import VISIT_SCHEDULE, LAST_INTERACTION_LIST, EMPTY_FIELD, CM7, PM3,\
    CM_APP_CM_MODULE, OUTPUT_DATE_FORMAT, INPUT_DATE_FORMAT
from custom.succeed.utils import is_succeed_admin, SUCCEED_CM_APPNAME, has_any_role, get_app_build, SUCCEED_DOMAIN
import logging
import simplejson


class PatientListReportDisplay(CaseDisplay):
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
        self.app_dict = get_cloudcare_app(report.domain, SUCCEED_CM_APPNAME)
        self.latest_build = get_app_build(self.app_dict)
        super(PatientListReportDisplay, self).__init__(report, case_dict)

    def get_property(self, key):
        if key in self.case:
            return self.case[key]
        else:
            return EMPTY_FIELD

    @property
    def case_name(self):
        return self.get_property("full_name")

    @property
    def case_link(self):
        url = self.case_detail_url
        if url:
            return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (url, html.escape(self.case_name)))
        else:
            return "%s (bad ID format)" % self.case_name

    @property
    def edit_link(self):
        module = self.app_dict['modules'][CM_APP_CM_MODULE]
        form_idx = [ix for (ix, f) in enumerate(module['forms']) if f['xmlns'] == CM7][0]
        return html.mark_safe("<a target='_blank' class='ajax_dialog' href='%s'>Edit</a>") \
            % html.escape(get_cloudcare_form_url(domain=self.app_dict['domain'],
                                                 app_build_id=self.latest_build,
                                                 module_id=CM_APP_CM_MODULE,
                                                 form_id=form_idx,
                                                 case_id=self.case_id) + '/enter/')

    @property
    def case_detail_url(self):
        return html.escape(
            PatientInteractionsReport.get_url(*[self.case["domain"]]) + "?patient_id=%s" % self.case["_id"])

    @property
    def mrn(self):
        return self.get_property("mrn")

    @property
    def randomization_date(self):
        rand_date = self.get_property("randomization_date")
        if rand_date != EMPTY_FIELD:
            date = datetime.strptime(rand_date, INPUT_DATE_FORMAT)
            return date.strftime(OUTPUT_DATE_FORMAT)
        else:
            return EMPTY_FIELD

    @property
    def visit_name(self):
        next_visit = getattr(self, "next_visit", EMPTY_FIELD)
        if next_visit == 'last':
            return _('No more visits')
        else:
            return next_visit['visit_name']

    @property
    def target_date(self):
        next_visit = getattr(self, "next_visit", EMPTY_FIELD)
        if next_visit != 'last':
            rand_date = dateutil.parser.parse(self.randomization_date)
            tg_date = ((rand_date.date() + timedelta(days=next_visit['days'])) - datetime.now().date()).days
            if tg_date >= 7:
                return (rand_date.date() + timedelta(days=next_visit['days'])).strftime("%m/%d/%Y")
            elif 7 > tg_date > 0:
                return "<span style='background-color: #FFFF00;padding: 5px;display: block;'> In %s day(s)</span>" % tg_date
            elif tg_date == 0:
                return "<span style='background-color: #FFFF00;padding: 5px;display: block;'>Today</span>"
            else:
                return "<span style='background-color: #FF0000; color: white;padding: 5px;display: block;'>%s day(s) overdue</span>" % (
                    tg_date * (-1))
        else:
            return EMPTY_FIELD

    @property
    def most_recent(self):
        return self.get_property("BP_category")

    @property
    def discuss(self):
        return self.get_property("discuss")

    @property
    def patient_info(self):
        if getattr(self, 'last_interaction', False) and self.last_interaction != EMPTY_FIELD:
            date = datetime.strptime(self.last_interaction, "%Y-%m-%dT%H:%M:%SZ")
            return date.strftime(OUTPUT_DATE_FORMAT)
        else:
            return EMPTY_FIELD

    @property
    def care_team(self):
        group = Group.by_user(self.case['owner_id'], wrap=False, include_names=True)
        if not group:
            try:
                group = Group.get(self.case['owner_id'])
            except ResourceNotFound:
                group = dict(name="No Group")
        if isinstance(group, list):
            group = group[0]
        return group['name']

    @property
    def tasks(self):
        url = html.escape(
            PatientTaskListReport.get_url(*[self.case["domain"]]) +
            "?patient_id=%s&task_status=open" % self.case["_id"])
        if url:
            return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>Tasks</a>" % url)
        else:
            return "%s (bad ID format)" % self.case_name


class PatientListReport(CustomProjectReport, CaseListReport):

    ajax_pagination = True
    name = ugettext_noop('Patient List')
    slug = 'patient_list'
    default_sort = {'target_date': 'asc'}
    base_template_filters = 'succeed/report.html'
    default_case_type = 'participant'

    fields = ['custom.succeed.fields.CareSite',
              'custom.succeed.fields.PatientStatus',
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
            DataTablesColumn(_("Modify Schedule"), sortable=False),
            DataTablesColumn(_("Name"), prop_name="name.exact"),
            DataTablesColumn(_("MRN"), prop_name="mrn.#value"),
            DataTablesColumn(_("Randomization Date"), prop_name="randomization_date.#value"),
            DataTablesColumn(_("Visit Name"), prop_name='visit_name'),
            DataTablesColumn(_("Target Date"), prop_name='target_date'),
            DataTablesColumn(_("Most Recent BP"), prop_name="BP_category.#value"),
            DataTablesColumn(_("Last Patient Interaction"), prop_name="last_interaction"),
            DataTablesColumn(_("Tasks"), prop_name="tasks", sortable=False),
            DataTablesColumn(_("Care Team"), prop_name="care_team")
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
    def groups(self):
        return Group.by_domain(SUCCEED_DOMAIN)

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
        sorting_block = self.get_sorting_block()[0].keys()[0] if len(self.get_sorting_block()) != 0 else None
        order = self.get_sorting_block()[0].values()[0] if len(self.get_sorting_block()) != 0 else None
        search_string = SearchFilter.get_value(self.request, self.domain)
        es_filters = q["query"]["filtered"]["filter"]
        if sorting_block == 'last_interaction':
            sort = {
                "_script": {
                    "script":
                        """
                            last=0;
                            break = true;
                            for (i = _source.actions.size(); (i > 0 && break); i--){
                                if (inter_list.contains(_source.actions[i-1].get('xform_xmlns'))) {
                                    last = _source.actions[i-1].get('date');
                                    break = false;
                                }
                            }
                            return last;
                        """,
                    "type": "string",
                    "params": {
                        "inter_list": LAST_INTERACTION_LIST
                    },
                    "order": order
                }
            }
            q['sort'] = sort
        elif sorting_block == 'target_date':
            sort = {
                "_script": {
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
                            Calendar cal = Calendar.getInstance();

                            r = _source.randomization_date.get('#value').split('-');
                            int year = Integer.parseInt(r[0]);
                            int month = Integer.parseInt(r[1]);
                            int day = Integer.parseInt(r[2]);
                            cal.set(year, month-1, day);
                            nv=(cal.getTimeInMillis() + (next_visit.get('days') * 24 * 60 * 60 * 1000));
                            return Calendar.getInstance().getTimeInMillis() - nv;
                        """,
                    "type": "number",
                    "params": {
                        "visits_list": VISIT_SCHEDULE
                    },
                    "order": order
                }
            }
            q['sort'] = sort
        elif sorting_block == 'visit_name':
            sort = {
                "_script": {
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
                            return next_visit.get('visit_name');
                        """,
                    "type": "string",
                    "params": {
                        "visits_list": VISIT_SCHEDULE
                    },
                    "order": order
                }
            }
            q['sort'] = sort
        elif sorting_block == 'care_team':
            ids_and_names = {}
            user_ids = {}

            users = []
            for g in self.groups:
                ids_and_names.update({g.get_id: g.name})
                for user in g.users:
                    users.append(user)
                    if user not in user_ids:
                        user_ids.update({user: g.name})
            sort = {
                "_script": {
                    "script":
                        """
                            owner=_source.owner_id;
                            grp_name=user_ids.get(owner);
                            if (grp_name==null) {
                               grp_name=ids_and_names.get(owner);
                            }
                            return grp_name;
                        """,
                    "type": "string",
                    "params": {
                        "user_ids": user_ids,
                        "ids_and_names": ids_and_names
                    },
                    "order": order
                }
            }
            q['sort'] = sort

        care_site = self.request_params.get('care_site_display', '')
        if care_site != '':
            query_block = {"queryString": {"default_field": "care_site_display.#value", "query": "*" + care_site + "*"}}
            q["query"]["filtered"]["query"] = query_block

        patient_status = self.request_params.get('patient_status', '')
        if patient_status != '':
            active_dict = {
                "nested": {
                    "path": "actions",
                    "filter": {
                        "bool" : {
                            "must_not": [],
                            "must": []

                        }
                    }
                }
            }
            if patient_status == 'active':
                active_dict['nested']['filter']['bool']['must_not'] = {"term": {"actions.xform_xmlns": PM3}}
            else:
                active_dict['nested']['filter']['bool']['must'] = {"term": {"actions.xform_xmlns": PM3}}
            es_filters["and"].append(active_dict)

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
            es_filters["and"].append({"term": {"type.exact": 'participant'}})
        if search_string:
            query_block = {"queryString": {"default_field": "full_name.#value",
                                           "query": "*" + search_string + "*"}}
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
        case_displays = (PatientListReportDisplay(self, restore_property_dict(self.get_case(case)))
                         for case in self.es_results['hits'].get('hits', []))

        for disp in case_displays:
            yield [
                disp.edit_link,
                disp.case_link,
                disp.mrn,
                disp.randomization_date,
                disp.visit_name,
                disp.target_date,
                disp.most_recent,
                disp.patient_info,
                disp.tasks,
                disp.care_team
            ]

    @property
    def user_filter(self):
        return super(PatientListReport, self).user_filter
