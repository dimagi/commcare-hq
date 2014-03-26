from datetime import datetime, timedelta
from django.core.urlresolvers import NoReverseMatch, reverse
from django.utils.translation import ugettext as _, ugettext_noop
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.api.es import ReportCaseES
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.cloudcare.api import get_cloudcare_app
from corehq.apps.groups.models import Group
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.elastic import es_query
from corehq.pillows.base import restore_property_dict
from django.utils import html
import dateutil
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from custom.succeed.reports import VISIT_SCHEDULE, LAST_INTERACTION_LIST, EMPTY_FIELD, CM7, PM3, CM_MODULE, \
    OUTPUT_DATE_FORMAT, INPUT_DATE_FORMAT
from custom.succeed.reports.patient_details import PatientInfoReport
from custom.succeed.utils import CONFIG, _is_succeed_admin, SUCCEED_CLOUD_APPNAME
import logging
import simplejson
from casexml.apps.case.models import CommCareCase


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
        self.app_dict = get_cloudcare_app(report.domain, SUCCEED_CLOUD_APPNAME)
        self.latest_build = ApplicationBase.get_latest_build(report.domain, self.app_dict['_id'])['_id']
        super(PatientListReportDisplay, self).__init__(report, case_dict)
        self.update_target_date_case_properties()

    def get_property(self, key):
        if key in self.case:
            return self.case[key]
        else:
            return EMPTY_FIELD

    @property
    def case_name(self):
        return self.case["full_name"]

    @property
    def case_link(self):
        url = self.case_detail_url
        if url:
            return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (url, html.escape(self.case_name)))
        else:
            return "%s (bad ID format)" % self.case_name

    def update_target_date_case_properties(self):
        case = CommCareCase.get(self.case_id)
        for visit_key, visit in enumerate(VISIT_SCHEDULE):
            try:
                next_visit = VISIT_SCHEDULE[visit_key + 1]
            except IndexError:
                next_visit = 'last'
            if next_visit != 'last':
                rand_date = dateutil.parser.parse(self.randomization_date)
                tg_date = rand_date.date() + timedelta(days=next_visit['days'])
                case.set_case_property(visit['target_date_case_property'], tg_date.strftime("%m/%d/%Y"))
        case.save()

    @property
    def edit_link(self):
        base_url = '/a/%(domain)s/cloudcare/apps/view/%(build_id)s/%(module_id)s/%(form_id)s/case/%(case_id)s/enter/'
        module = self.app_dict['modules'][CM_MODULE]
        form_idx = [ix for (ix, f) in enumerate(module['forms']) if f['xmlns'] == CM7][0]
        return html.mark_safe("<a class='ajax_dialog' href='%s'>Edit</a>") \
            % html.escape(base_url % dict(
                form_id=form_idx,
                case_id=self.case_id,
                domain=self.app_dict['domain'],
                build_id=self.latest_build,
                module_id=CM_MODULE
            )
        )

    @property
    def case_detail_url(self):
        return html.escape(
                PatientInfoReport.get_url(*[self.case["domain"]]) + "?patient_id=%s" % self.case["_id"])


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
        if self.last_interaction != EMPTY_FIELD:
            date = datetime.strptime(self.last_interaction, "%Y-%m-%dT%H:%M:%SZ")
            return date.strftime(OUTPUT_DATE_FORMAT)
        else:
            return EMPTY_FIELD


class PatientListReport(CustomProjectReport, CaseListReport):

    ajax_pagination = True
    include_inactive = True
    name = ugettext_noop('Patient List')
    slug = 'patient_list'
    default_sort = {'target_date': 'asc'}

    fields = ['custom.succeed.fields.CareSite',
              'custom.succeed.fields.ResponsibleParty',
              'custom.succeed.fields.PatientStatus']

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
            DataTablesColumn(_("Discuss at Huddle?"), prop_name="discuss.#value"),
            DataTablesColumn(_("Last Patient Interaction"), prop_name="last_interaction"),
        )
        return headers

    @property
    @memoized
    def es_results(self):
        q = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}}
                    ],
                    "must_not": []
                }
            },
            'sort': self.get_sorting_block(),
            'from': self.pagination.start,
            'size': self.pagination.count,
        }
        sorting_block = self.get_sorting_block()[0].keys()[0] if len(self.get_sorting_block()) != 0 else None
        order = self.get_sorting_block()[0].values()[0] if len(self.get_sorting_block()) != 0 else None


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

        care_site = self.request_params.get('care_site', '')
        if care_site != '':
            q["query"]["bool"]["must"].append({"match": {"care_site.#value": care_site}})
        else:
            if not isinstance(self.request.couch_user, WebUser) or _is_succeed_admin(self.request.couch_user):
                groups = self.request.couch_user.get_group_ids()
                party = []
                for group_id in groups:
                    group = Group.get(group_id)
                    for grp in CONFIG['groups']:
                        if group.name == grp['text']:
                            party.append(grp['val'])
                q["query"]["bool"]["must"].append({"terms": {"care_site.#value": party, "minimum_should_match": 1}})

        patient_status = self.request_params.get('patient_status', '')
        if patient_status != '':
            active_dict = {"nested": {
                "path": "actions",
                "query": {
                    "match": {
                        "actions.xform_xmlns": PM3}}}}
            if patient_status == "active":
                q["query"]["bool"]["must_not"].append(active_dict)
            else:
                q["query"]["bool"]["must"].append(active_dict)

        responsible_party = self.request_params.get('responsible_party', '')
        if responsible_party != '':
            users = [user.get_id for user in CommCareUser.by_domain(domain=self.domain) if 'role' in user.user_data and user.user_data['role'] == responsible_party.upper()]
            terms = {"terms": {"user_id": users, "minimum_should_match": 1}}
            q["query"]["bool"]["must"].append(terms)

        if self.case_type:
            q["query"]["bool"]["must"].append({"match": {"type.exact": 'participant'}})
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(q)))
        return es_query(q=q, es_url=REPORT_CASE_INDEX + '/_search', dict_only=False)

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
                disp.discuss,
                disp.patient_info
            ]

    @property
    def user_filter(self):
        return super(PatientListReport, self).user_filter