from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.reminders.models import REMINDER_TYPE_ONE_TIME
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import Axis, LineChart
from corehq.apps.sms.models import WORKFLOW_KEYWORD, WORKFLOW_REMINDER, WORKFLOW_BROADCAST
from corehq.elastic import es_query, ES_URLS, es_histogram
from custom.trialconnect.reports import TrialConnectReport
from dimagi.utils.couch.database import get_db

WORKFLOWS = [WORKFLOW_KEYWORD, WORKFLOW_REMINDER, WORKFLOW_BROADCAST]
NA = 'N/A'

class BaseSystemOverviewReport(TrialConnectReport):
    need_group_ids = True
    fields = [
        'corehq.apps.reports.filters.select.MultiGroupFilter',
        'corehq.apps.reports.filters.select.MultiCaseGroupFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

class SystemOverviewReport(BaseSystemOverviewReport):
    slug = 'system_overview'
    name = ugettext_noop("System Overview")
    description = ugettext_noop("Description for System Overview Report")
    section_name = ugettext_noop("System Overview")

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
        return DataTablesHeader(
            DataTablesColumn("", sortable=False),
            DataTablesColumn(_("Number")),
            DataTablesColumn(_("Mobile Worker Messages")),
            DataTablesColumn(_("Case Messages")),
            DataTablesColumn(_("Incoming")),
            DataTablesColumn(_("Outgoing")),
        )

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
                elif term['term'] == 'couchuser':
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
                data = get_db().view('reminders/handlers_by_reminder_type',
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
            row(_("Unknown")),
        ]

        def total(index):
            return sum([l[index] for l in rows if l[index] != NA])

        self.total_row = [_("Total"), total(1), total(2), total(3), total(4), total(5)]

        return rows

    def es_histogram(self, workflow):
        q = {"query": {"term": {"workflow": workflow.lower()}}}
        return es_histogram(histo_type="sms", domains=[self.domain], q=q,
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

class SystemUsersReport(BaseSystemOverviewReport):
    slug = 'system_users'
    name = ugettext_noop("System Users")
    description = ugettext_noop("Description for System Users Report")
    section_name = ugettext_noop("System Users")

    def active_query(self, recipient_type):
        q = self.base_query
        q["query"]["bool"]["must"].append({"term": {"direction": "i"}})
        q["query"]["bool"]["must"].append({"term": {"couch_recipient_doc_type": recipient_type}})
        return es_query(q=q, facets=['couch_recipient'], es_url=ES_URLS['sms'], size=0)

    def messages_query(self):
        q = self.base_query
        facets = ['couch_recipient_doc_type']
        return es_query(q=q, facets=facets, es_url=ES_URLS['sms'], size=0)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Users", sortable=False),
            DataTablesColumn(_("Mobile Workers")),
            DataTablesColumn(_("Cases")),
            DataTablesColumn(_("Total")),
        )

    @property
    def rows(self):
        def row(header, mw_val, case_val):
            return [_(header), mw_val, case_val, mw_val + case_val]

        def verified_numbered_users(owner_type):
            owners = get_db().view('sms/verified_number_by_domain',
                reduce=True,
                group=True,
                startkey=[self.domain, owner_type],
                endkey=[self.domain, owner_type, {}],
            ).all()
            return len(owners)

        number = row("Number", verified_numbered_users("CommCareUser"), verified_numbered_users("CommCareCase"))

        def get_actives(recipient_type):
            return len(self.active_query(recipient_type)['facets']['couch_recipient']['terms'])

        def div(num, denom):
            return num / denom if denom != 0 else 0

        active = row("Active", get_actives("commcareuser"), get_actives("commcarecase"))

        perc_active = [_("% Active"),
                       div(active[1], number[1]), div(active[2], number[2]), div(active[3], number[3])]

        facets = self.messages_query()['facets']
        to_users, to_cases = 0, 0
        for term in facets['couch_recipient_doc_type']['terms']:
            if term['term'] == 'commcarecase':
                to_cases = term['count']
            elif term['term'] == 'couchuser':
                to_users = term['count']
        messages = row("Messages", to_users, to_cases)

        avg_per_user = [_("Avg per User"),
                        div(messages[1], number[1]), div(messages[2], number[2]), div(messages[3], number[3])]
        avg_per_act_user = [_("Avg per Active User"),
                            div(messages[1], active[1]), div(messages[2], active[2]), div(messages[3], active[3])]

        return [number, active, perc_active, messages, avg_per_user, avg_per_act_user]
