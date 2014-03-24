import uuid
from django.utils.translation import ugettext_noop, ugettext as _
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.standard import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from django.core.urlresolvers import reverse, NoReverseMatch
from django.utils import html
from dimagi.utils.decorators.memoized import memoized


class CareplanCaseDisplay(CaseDisplay):
    @property
    def case_detail_url(self):
        try:
            return html.escape(self.report.case_detail_url(self.case_id))
        except NoReverseMatch:
            return None


class CareplanCaseListReport(CaseListReport):
    name = ugettext_noop('Care Plan Case List')
    slug = "careplan_caselist"

    fields = [
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.SelectCaseOwnerField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
    ]

    def case_detail_url(self, case_id):
        return self.sub_report.get_url(self.domain) + "?patient_id=%s" % case_id

    @property
    def rows(self):
        for data in self.get_data():
            display = CareplanCaseDisplay(self, data['_case'])
            yield [
                display.case_type,
                display.case_link,
                display.owner_display,
                display.opened_on,
                display.creating_user,
                display.modified_on,
                display.closed_display
            ]


class CareplanReport(ProjectReport, GenericReportView, ProjectReportParametersMixin):
    slug = "careplan_patient"
    description = "some patient"

    hide_filters = True
    fields = []
    flush_layout = True
    report_template_path = ""

    name = "Care Plan"

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False

    @memoized
    def get_case(self):
        if self.request.GET.get('patient_id', None) is None:
            return None
        return CommCareCase.get(self.request.GET['patient_id'])

    @property
    def report_context(self):
        ret = {}

        try:
            patient_doc = self.get_case()
            has_error = False
        except Exception:
            has_error = True
            patient_doc = None

        if patient_doc is None:
            self.report_template_path = "reports/careplan/nopatient.html"
            if has_error:
                ret['error_message'] = "Patient not found"
            else:
                ret['error_message'] = "No patient selected"
            return ret

        ret['patient_doc'] = patient_doc

        ret.update({
            'case_hierarchy_options': {
                "show_view_buttons": False,
                "get_case_url": lambda case_id: reverse('case_details', args=[self.domain, case_id]),
                "columns": self.related_cases_columns,
                "related_type_info": self.related_type_info
            },
            'case': patient_doc,
        })
        self.report_template_path = "reports/careplan/patient_careplan.html"
        return ret

    @property
    def related_cases_columns(self):
        return [
            {
                'name': _('Status'),
                'expr': "status",
            },
            {
                'name': _('Follow-Up Date'),
                'expr': "date_followup",
                'parse_date': True,
                'timeago': True,
            },
            {
                'name': _('Date Modified'),
                'expr': "modified_on",
                'parse_date': True,
                'timeago': True,
            }
        ]

    @property
    def related_type_info(self):
        case_type = self.get_case().type
        goal_conf = {
            'type_name': _("Goal"),
            'open_sortkeys': [['date_followup', 'asc']],
            'closed_sortkeys': [['closed_on', 'desc']],

            "app_id": self.careplan_app_id,
            "case_id_attr": "case_id_goal",
            "child_type": "careplan_task",
            "description_property": "description",
            "create_session_data": {
                "case_id_goal": str(uuid.uuid4())
            },
        }
        goal_conf.update(self.config.goal_conf)
        task_conf = {
            'type_name': _("Task"),
            'open_sortkeys': [['date_followup', 'asc']],
            'closed_sortkeys': [['closed_on', 'desc']],

            'app_id': self.careplan_app_id,
            "case_id_attr": "case_id_task",
            "description_property": "description",
            "ignore_relationship_types": [case_type]
        }
        task_conf.update(self.config.task_conf)
        return {
            case_type: {
                "case_id_attr": "case_id",
                "child_type": "careplan_goal",
            },
            "careplan_goal": goal_conf,
            "careplan_task": task_conf,
        }


def make_careplan_reports(config):
    for conf in config.app_configs.values():
        class AppCareplanReport(CareplanReport):
            slug = '{0}_{1}'.format(CareplanReport.slug, conf.latest_release)
            careplan_app_id = conf.latest_release
            config = conf

        class AppCareplanListReport(CareplanCaseListReport):
            name = conf.name
            slug = '{0}_{1}'.format(CareplanCaseListReport.slug, conf.latest_release)
            default_case_type = conf.case_type
            sub_report = AppCareplanReport

        yield AppCareplanListReport
        yield AppCareplanReport