from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.reminders.models import REMINDER_TYPE_ONE_TIME
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from corehq.apps.sms.models import WORKFLOW_KEYWORD, WORKFLOW_REMINDER, WORKFLOW_BROADCAST
from corehq.elastic import es_query, ES_URLS
from dimagi.utils.couch.database import get_db

WORKFLOWS = [WORKFLOW_KEYWORD, WORKFLOW_REMINDER, WORKFLOW_BROADCAST]
NA = 'N/A'

class SystemOverviewReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    slug = 'system_overview'
    name = ugettext_noop("System Overview")
    description = ugettext_noop("Description for System Overview Report")
    section_name = ugettext_noop("System Overview")
    need_group_ids = True
    is_cacheable = True
    fields = [
        'corehq.apps.reports.filters.select.MultiGroupFilter',
        'corehq.apps.reports.filters.select.MultiCaseGroupFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]
    emailable = True

    @property
    def base_query(self):
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {
                            'date': {
                                "from": self.datespan.startdate_param,
                                "to": self.datespan.enddate_param,
                                "include_upper": True}}}]}}}

        if self.users_by_group:
            q["query"]["bool"]["must"].append({"in": {"couch_recipient": self.combined_user_ids}})
        if self.cases_by_case_group:
            q["query"]["bool"]["must"].append({"in": {"couch_recipient": self.cases_by_case_group}})

        return q

    def workflow_query(self, workflow=None, additional_facets=None):
        additional_facets = additional_facets or []

        q = self.base_query

        if workflow:
            q["filter"] = {"and": [{"term": {"workflow": workflow}}]}
        else:
            q["filter"] = {"and": [{"not": {"in": {"workflow": WORKFLOWS}}}]}

        facets = ['couch_recipient_doc_type', 'direction'] + additional_facets
        return es_query(q=q, facets=facets, es_url=ES_URLS['sms'], size=0)

    def active_query(self, recipient_type):
        q = self.base_query
        q["query"]["bool"]["must"].append({"term": {"direction": "i"}})
        q["query"]["bool"]["must"].append({"term": {"couch_recipient_doc_type": recipient_type}})
        return es_query(q=q, facets=['couch_recipient'], es_url=ES_URLS['sms'], size=0)

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

        def get_actives(recipient_type):
            # print self.active_query(recipient_type)['facets']
            return len(self.active_query(recipient_type)['facets']['couch_recipient']['terms'])

        active_users = get_actives('commcareuser')
        active_cases = get_actives('commcarecase')

        print "\n===================="
        print "Active Users: %s" % active_users
        print "Active Cases: %s" % active_cases
        print "====================\n"

        return rows

