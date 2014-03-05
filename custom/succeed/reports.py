from datetime import datetime, timedelta
from django.core.urlresolvers import NoReverseMatch, reverse
from django.utils.translation import ugettext as _, ugettext_noop
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.api.es import ReportCaseES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.elastic import es_query
from corehq.pillows.base import restore_property_dict
from django.utils import html
import dateutil
from casexml.apps.case.models import CommCareCase
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX

EMPTY_FIELD = "---"

PM1 = 'http://openrosa.org/formdesigner/111B09EB-DFFA-4613-9A16-A19BA6ED7D04'
PM2 = 'http://openrosa.org/formdesigner/4B52ADB2-AA79-4056-A13E-BB34871876A1'
PM3 = 'http://openrosa.org/formdesigner/5250590B-2EB2-46A8-9943-B7008CDA2BB9'
PM4 = 'http://openrosa.org/formdesigner/876cec8f07c0e29b9f9e2bd0b33c5c85bf0192ee'
CM1 = 'http://openrosa.org/formdesigner/9946952C-A2EB-43D5-A500-B386C56A49A7'
CM2 = 'http://openrosa.org/formdesigner/BCFFFE7E-8C93-4B4E-9589-FF12C710C255'
CM3 = 'http://openrosa.org/formdesigner/4EA3D459-7FB6-414F-B106-05E6E707568B'
CM4 = 'http://openrosa.org/formdesigner/263cc99e9f0cdbc55d307359c7b45a1e555f35d1'
CM5 = 'http://openrosa.org/formdesigner/8abd54794d8c5d592100b8cdf1f642903b7f4abe'
CM6 = 'http://openrosa.org/formdesigner/9b47556945c6476438c2ac2f0583e2ca0055e46a'
CM7 = 'http://openrosa.org/formdesigner/4b924f784e8dd6a23045649730e82f6a2e7ce7cf'
HUD1 = 'http://openrosa.org/formdesigner/24433229c5f25d0bd3ceee9bf70c72093056d1af'
HUD2 = 'http://openrosa.org/formdesigner/63f8287ac6e7dce0292ebac9b232b0d3bde327dc'
PD1 = 'http://openrosa.org/formdesigner/9eb0eaf6954791425d6d5f0b66db9a484cacd264'
PD2 = 'http://openrosa.org/formdesigner/69751bf3078369491e1c2f1e3c874895f762a4c1'
CHW1 = 'http://openrosa.org/formdesigner/4b368b1d73862abeca3bce67b6e09724b8dca850'
CHW2 = 'http://openrosa.org/formdesigner/cbc4e37437945bfda04e391d11006b6d02c24fc2'
CHW3 = 'http://openrosa.org/formdesigner/5d77815bf7631a527d8647cdbaa5971e367f6548'
CHW4 = 'http://openrosa.org/formdesigner/f8a741808584d772c4b899ef84db197da5b4d12a'
CUSTOM_EDIT = 'http://commcarehq.org/cloudcare/custom-edit'

VISIT_SCHEDULE = [
    {
        'visit_name': _('CM Initial contact form'),
        'xmlns': CM1,
        'days': 5
    },
    {
        'visit_name': _('CM Medical Record Review'),
        'xmlns': CM2,
        'days': 7
    },
    {
        'visit_name': _('Cm 1-week Telephone Call'),
        'xmlns': CM3,
        'days': 10
    },
    {
        'visit_name': _('CM Initial huddle'),
        'xmlns': HUD1,
        'days': 21
    },
    {
        'visit_name': _('CM Home Visit 1'),
        'xmlns': CHW1,
        'days': 35
    },
    {
        'visit_name': _('CM Clinic Visit 1'),
        'xmlns': CM4,
        'days': 49
    },
    {
        'visit_name': _('CM Home Visit 2'),
        'xmlns': CHW2,
        'days': 100
    },
    {
        'visit_name': _('CM Clinic Visit 2'),
        'xmlns': CM5,
        'days': 130
    },
    {
        'visit_name': _('CHW CDSMP tracking'),
        'xmlns': CHW4,
        'days': 135
    },
    {
        'visit_name': _('CM Home Visit 3'),
        'xmlns': CHW2,
        'days': 200
    },
    {
        'visit_name': _('CM Clinic Visit 3'),
        'xmlns': CM5,
        'days': 250
    },
]

LAST_INTERACTION_LIST = [PM1, PM3, CM1, CM3, CM4, CM5, CM6, CHW1, CHW2, CHW3, CHW4]


class PatientListReportDisplay(CaseDisplay):
    def __init__(self, report, case_dict):
        case = CommCareCase.get(case_dict["_id"])
        forms = case.get_forms()
        next_visit = VISIT_SCHEDULE[0]
        last_inter = []
        for form in forms:
            if form.xmlns in LAST_INTERACTION_LIST:
                last_inter.append(form)

        last_inter.sort(key=lambda form: form.received_on)
        for visit_key, visit in enumerate(VISIT_SCHEDULE):
            for key, form in enumerate(forms):
                if visit['xmlns'] == form.xmlns:
                    try:
                        next_visit = VISIT_SCHEDULE[visit_key + 1]
                        del forms[key]
                        break
                    except IndexError:
                        next_visit = 'last'
        setattr(self, "next_visit", next_visit)
        if len(last_inter) == 0:
            setattr(self, "last_interaction", EMPTY_FIELD)
        else:
            setattr(self, "last_interaction", last_inter[len(last_inter) - 1].received_on)

        super(PatientListReportDisplay, self).__init__(report, case_dict)

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
            return html.mark_safe("<a class='ajax_dialog' href='' target='_blank'>%s</a>" % html.escape(self.case_name))
        else:
            return "%s (bad ID format)" % self.case_name

    @property
    def edit_link(self):
        try:
            return html.mark_safe("<a class='ajax_dialog' href=''>Edit</a>")
        except NoReverseMatch:
            return "%s (bad ID format)"

    @property
    def case_detail_url(self):
        try:
            return reverse('case_details', args=[self.report.domain, self.case_id])
        except NoReverseMatch:
            return None

    @property
    def mrn(self):
        return self.get_property("mrn")

    @property
    def randomization_date(self):
        date = datetime.strptime(self.get_property("randomization_date"), "%Y-%m-%d")
        return date.strftime("%m/%d/%Y")

    @property
    def visit_name(self):
        next_visit = getattr(self, "next_visit", EMPTY_FIELD)
        if next_visit == 'last':
            return _('No More visits')
        else:
            return next_visit['visit_name']

    @property
    def target_date(self):
        next_visit = getattr(self, "next_visit", EMPTY_FIELD)
        if next_visit != 'last':
            rand_date = dateutil.parser.parse(self.randomization_date)
            tg_date = ((rand_date.date() + timedelta(days=next_visit['days'])) - datetime.now().date()).days
            if tg_date >= 7:
                return (rand_date.date() + timedelta(days=next_visit['days'])).date()
            elif 7 > tg_date > 0:
                return "<span style='background-color: #FFFF00;padding: 5px;display: block;'> In %s day(s)</span>" % tg_date
            elif tg_date == 0:
                return "<span style='background-color: #FFFF00;padding: 5px;display: block;'>Today</span>" % tg_date
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
        date = getattr(self, "last_interaction", EMPTY_FIELD)
        if date != EMPTY_FIELD:
            return date.strftime("%m/%d/%Y")
        else:
            return EMPTY_FIELD


class PatientListReport(CustomProjectReport, CaseListReport):
    ajax_pagination = True
    include_inactive = True
    name = ugettext_noop('Patient List')
    slug = 'patient_list'

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
    def case_owners(self):
        return None

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
            DataTablesColumn(_("Visit Name")),
            DataTablesColumn(_("Target Date")),
            DataTablesColumn(_("Most Recent BP"), prop_name="BP_category.#value"),
            DataTablesColumn(_("Discuss at Huddle?"), prop_name="discuss.#value"),
            DataTablesColumn(_("Last Patient Interaction")),

        )
        return headers

    def es_case_queries(self, dict_only=False):
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
        }
        care_site = self.request_params.get('care_site', '')
        if care_site != '':
            q["query"]["bool"]["must"].append({"match": {"care_site.#value": care_site}})
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

        if self.case_type:
            q["query"]["bool"]["must"].append({"match": {"type.exact": 'participant'}})
        return es_query(q=q, es_url=REPORT_CASE_INDEX + '/_search', dict_only=dict_only)["hits"]["hits"]

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