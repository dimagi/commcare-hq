from django.core.urlresolvers import reverse
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.userreports.sql import get_table_name
from custom.succeed.reports.patient_details import PatientDetailsReport
from django.utils import html


class PatientSubmissionData(SqlData):
    slug = 'succeed_submissions'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], self.slug)

    @property
    def columns(self):
        return [
            DatabaseColumn('Doc Id', SimpleColumn('doc_id')),
            DatabaseColumn('Form name', SimpleColumn('form_name')),
            DatabaseColumn('Submitted By', SimpleColumn('username')),
            DatabaseColumn('Completed', SimpleColumn('date')),
        ]

    @property
    def filters(self):
        return [EQ('case_id', 'case_id')]

    @property
    def group_by(self):
        return ['doc_id', 'form_name', 'username', 'date']


class PatientSubmissionReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    slug = "patient_submissions"
    name = 'Patient Submissions'
    use_datatables = True
    hide_filters = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        if domain and project and user is None:
            return True
        return False

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'case_id': self.request.GET.get('patient_id'),
        }

    @property
    def model(self):
        return PatientSubmissionData(config=self.report_config)

    @property
    def fields(self):
        return []

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Form Name", prop_name='@name'),
            DataTablesColumn("Submitted By", prop_name='form.meta.username'),
            DataTablesColumn("Completed", prop_name='received_on')
        )

    @property
    def rows(self):
        if self.request.GET.has_key('patient_id'):
            def _format_row(row_field_dict):
                return [
                    self.submit_history_form_link(row_field_dict["doc_id"],
                                                  row_field_dict['form_name']),
                    row_field_dict['username'],
                    row_field_dict['date']
                ]

            rows = self.model.get_data()
            for row in rows:
                yield list(_format_row(row))

    def submit_history_form_link(self, form_id, form_name):
        url = reverse('render_form_data', args=[self.domain, form_id])
        return html.mark_safe("<a class='ajax_dialog' href='%s'"
                              "target='_blank'>%s</a>" % (url, html.escape(form_name)))

    @property
    def report_context(self):
        ret = super(PatientSubmissionReport, self).report_context
        ret['view_mode'] = 'submissions'
        tabular_context = PatientDetailsReport(self.request).report_context
        tabular_context.update(ret)
        self.report_template_path = "patient_submissions.html"
        tabular_context['patient_id'] = self.request_params['patient_id']
        return tabular_context
