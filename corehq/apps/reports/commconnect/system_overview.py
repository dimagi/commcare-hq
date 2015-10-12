from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.reminders.models import REMINDER_TYPE_ONE_TIME, CaseReminderHandler
from corehq.apps.reports.commconnect import div, CommConnectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.graph_models import Axis, LineChart
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import WORKFLOW_KEYWORD, WORKFLOW_REMINDER, WORKFLOW_BROADCAST
from corehq.elastic import es_query, ES_URLS, es_histogram
from dimagi.utils.couch.database import get_db

WORKFLOWS = [WORKFLOW_KEYWORD, WORKFLOW_REMINDER, WORKFLOW_BROADCAST]
NA = 'N/A'

class BaseSystemOverviewReport(CommConnectReport):
    fields = [
        'corehq.apps.reports.filters.select.MultiGroupFilter',
        'corehq.apps.reports.filters.select.MultiCaseGroupFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

class SystemOverviewReport(BaseSystemOverviewReport):
    slug = 'system_overview'
    name = ugettext_noop("Overview")
    description = ugettext_noop("Summary of the different types of messages sent and received by the system.")
    section_name = ugettext_noop("Overview")

    def workflow_query(self, workflow=None, additional_facets=None):
        additional_facets = additional_facets or []

        q = self.base_query

        if workflow:
            q["filter"] = {"and": [{"term": {"workflow": workflow.lower()}}]}
        else:
            q["filter"] = {"and": [{"not": {"in": {"workflow": [w.lower() for w in WORKFLOWS]}}}]}

        facets = ['couch_recipient_doc_type', 'direction'] + additional_facets
        return es_query(q=q, facets=facets, es_url=ES_URLS['sms'], size=0)

    @property
    def headers(self):
        columns = [
            DataTablesColumn("", sortable=False),
            DataTablesColumn(_("Number"), help_text=_("Number of individual items")),
        ]
        columns.append(DataTablesColumnGroup("",
            DataTablesColumn(_("Mobile Worker Messages"),
                             help_text=_("SMS Messages to or from mobile workers' phones, incoming and outgoing")),
            DataTablesColumn(_("Case Messages"),
                             help_text=_("SMS Messages to or from a phone number in a case, incoming and outgoing"))))
        columns.append(DataTablesColumnGroup("",
            DataTablesColumn(_("Incoming"), help_text=_("Total incoming SMS")),
            DataTablesColumn(_("Outgoing"), help_text=_("Total outgoing SMS"))))
        return DataTablesHeader(*columns)

    @property
    def rows(self):

        def row(rowname, workflow=None):
            additional_workflow_facets = {
                WORKFLOW_KEYWORD: ['xforms_session_couch_id'],
                WORKFLOW_REMINDER: ['reminder_id'],
            }
            additional_facets = additional_workflow_facets.get(workflow)
            facets = self.workflow_query(workflow, additional_facets)['facets']
            to_cases, to_users, outgoing, incoming = 0, 0, 0, 0

            for term in facets['couch_recipient_doc_type']['terms']:
                if term['term'] == 'commcarecase':
                    to_cases = term['count']
                elif term['term'] == 'commcareuser':
                    to_users = term['count']

            for term in facets['direction']['terms']:
                if term['term'] == 'o':
                    outgoing = term['count']
                elif term['term'] == 'i':
                    incoming = term['count']

            number = NA
            if workflow in additional_workflow_facets:
                number = len(facets[additional_workflow_facets[workflow][0]]["terms"])
            elif workflow == WORKFLOW_BROADCAST:
                key = [self.domain, REMINDER_TYPE_ONE_TIME]
                data = CaseReminderHandler.get_db().view('reminders/handlers_by_reminder_type',
                    reduce=True,
                    startkey=key + [self.datespan.startdate_param_utc],
                    endkey=key + [self.datespan.enddate_param_utc],
                ).one()
                number = data["value"] if data else 0

            return [rowname, number, to_users, to_cases, incoming, outgoing]

        rows =  [
            row(_("Keywords"), WORKFLOW_KEYWORD),
            row(_("Reminders"), WORKFLOW_REMINDER),
            row(_("Broadcasts"), WORKFLOW_BROADCAST),
            row(_("Other")),
        ]

        def total(index):
            return sum([l[index] for l in rows if l[index] != NA])

        self.total_row = [_("Total"), total(1), total(2), total(3), total(4), total(5)]

        return rows

    def es_histogram(self, workflow):
        q = {"query": {"bool": {"must": [{"term": {"workflow": workflow.lower()}}]}}}
        return es_histogram(histo_type="sms", domains=[self.domain], q=self.add_recipients_to_query(q),
                            startdate=self.datespan.startdate_display, enddate=self.datespan.enddate_display)

    @property
    def charts(self):
        chart = LineChart(_("Messages over time"), None, Axis(_('# of Messages'), ',.1d'))
        chart.data = {
            _("Keywords"): self.es_histogram(WORKFLOW_KEYWORD),
            _("Reminders"): self.es_histogram(WORKFLOW_REMINDER),
            _("Broadcasts"): self.es_histogram(WORKFLOW_BROADCAST),
        }
        chart.data_needs_formatting = True
        chart.x_axis_uses_dates = True
        return [chart]
