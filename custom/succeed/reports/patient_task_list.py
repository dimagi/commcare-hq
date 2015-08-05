from django.core.urlresolvers import reverse
from django.utils import html
from django.utils.translation import ugettext as _, ugettext_noop
from sqlagg.base import AliasColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, OR, IN
from corehq.apps.cloudcare.api import get_cloudcare_app, get_cloudcare_form_url
from corehq.apps.reports.sqlreport import SqlTabularReport, AggregateColumn, DatabaseColumn, DataFormatter, \
    TableDataFormat
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.userreports.sql import get_table_name
from custom.succeed.reports.patient_Info import PatientInfoReport
from custom.succeed.reports import EMPTY_FIELD, OUTPUT_DATE_FORMAT, \
    CM_APP_UPDATE_VIEW_TASK_MODULE, CM_UPDATE_TASK, TASK_RISK_FACTOR, TASK_ACTIVITY
from custom.succeed.utils import SUCCEED_CM_APPNAME, get_app_build
from dimagi.utils.decorators.memoized import memoized


class PatientTaskListReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    name = ugettext_noop('Patient Tasks')
    slug = 'patient_task_list'
    fields = ['custom.succeed.fields.ResponsibleParty',
              'custom.succeed.fields.PatientName',
              'custom.succeed.fields.TaskStatus']

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        super(PatientTaskListReport, self).__init__(request, base_context=base_context, domain=domain, **kwargs)
        self.app_dict = get_cloudcare_app(domain, SUCCEED_CM_APPNAME)
        self.latest_build = get_app_build(self.app_dict)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], self.slug)

    def get_link(self, url, field, doc_id):
        if url:
            return html.mark_safe(u"<a class='ajax_dialog' href='{0}' target='_blank'>{1}</a>".format(
                url, html.escape(field)))
        else:
            return "%s (bad ID format)" % doc_id

    def case_link(self, referenced_id, full_name):
        url = html.escape(
            PatientInfoReport.get_url(*[self.domain]) + "?patient_id=%s" % referenced_id)
        return self.get_link(url, full_name, referenced_id)

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

    def name_link(self, name, doc_id, is_closed):
        if is_closed:
            details_url = reverse('case_details', args=[self.domain, doc_id])
            url = details_url + '#!history'
        else:
            url = self.get_form_url(self.app_dict,
                                    self.latest_build,
                                    CM_APP_UPDATE_VIEW_TASK_MODULE,
                                    CM_UPDATE_TASK,
                                    doc_id)
        return self.get_link(url, name, doc_id)

    def task_due(self, task_due):
        if task_due and task_due != EMPTY_FIELD:
            return task_due.strftime(OUTPUT_DATE_FORMAT)
        else:
            return EMPTY_FIELD

    def last_modified(self, last_modified):
        if last_modified and last_modified != EMPTY_FIELD:
            return last_modified.strftime(OUTPUT_DATE_FORMAT)
        else:
            return EMPTY_FIELD

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    def config(self):
        responsible_party = self.request.GET.get('responsible_party', None)
        patient_id = self.request.GET.get('patient_id', None)
        task_status = self.request.GET.get('task_status')
        if task_status == 'open':
            task_status = '1'
        elif task_status == 'closed':
            task_status = '0'
        else:
            task_status = None
        user = self.request.couch_user
        owner_ids = tuple()
        user_id = None
        if not user.is_web_user():
            owner_ids = user.get_group_ids()
            user_id = user.get_id
        return {
            'domain': self.domain,
            'task_responsible': responsible_party,
            'referenced_id': patient_id,
            'closed': task_status,
            'owner_ids': tuple(owner_ids),
            'user_id': user_id,
        }

    @property
    def filters(self):
        filters = []
        if self.config['task_responsible']:
            filters.append(EQ('task_responsible', 'task_responsible'))
        if self.config['referenced_id']:
            filters.append(EQ('referenced_id', 'referenced_id'))
        if self.config['closed']:
            filters.append(EQ('closed', 'closed'))
        or_filter = []
        if self.config['owner_ids']:
            or_filter.append(IN('owner_id', 'owner_ids'))
        if or_filter:
            or_filter.append(EQ('user_id', 'user_id'))
            filters.append(OR(filters=or_filter))
        return filters

    @property
    def columns(self):
        return [
            AggregateColumn(_('Patient Name'), aggregate_fn=self.case_link,
                            columns=[SimpleColumn('referenced_id'), SimpleColumn('full_name')],
                            sortable=False),
            AggregateColumn(_('Task Name'), aggregate_fn=self.name_link,
                            columns=[SimpleColumn('name'), SimpleColumn('doc_id'), AliasColumn('is_closed')],
                            sortable=False),
            DatabaseColumn(_('Responsible Party'), SimpleColumn('task_responsible'),
                           format_fn=lambda x: x.upper(), sortable=False),
            DatabaseColumn(_('Status'), SimpleColumn('closed', alias='is_closed'),
                           format_fn=lambda x: 'Closed' if x == '0' else 'Open', sortable=False),
            DatabaseColumn(_('Action Due'), SimpleColumn('task_due'),
                           format_fn=self.task_due),
            DatabaseColumn(_('Last Updated'), SimpleColumn('last_updated'),
                           format_fn=self.last_modified),
            DatabaseColumn(_('Task Type'), SimpleColumn('task_activity'),
                           format_fn=lambda x: TASK_ACTIVITY.get(x, x)),
            DatabaseColumn(_('Associated Risk Factor'), SimpleColumn('task_risk_factor'),
                           format_fn=lambda x: TASK_RISK_FACTOR.get(x, x)),
            DatabaseColumn(_('Details'), SimpleColumn('task_details'), sortable=False)

        ]

    @property
    def group_by(self):
        return ['doc_id', 'referenced_id', 'full_name', 'is_closed', 'task_responsible',
                'task_due', 'last_updated', 'task_activity', 'task_risk_factor',
                'task_details', 'name']

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return formatter.format(self.data, keys=self.keys, group_by=self.group_by)

