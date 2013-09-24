from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from corehq.elastic import es_query, ES_URLS

WORKFLOWS = ["workflow_keyword", "workflow_reminder", "workflow_broadcast"]

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

    def query_sms(self, workflow=None):
        """
            Open cases that haven't been modified within time range
        """
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {
                            'date': {
                                "from": self.datespan.startdate_param,
                                "to": self.datespan.enddate_param,
                                "include_upper": True}}}]}}}

        if workflow:
            q["filter"] = {"and": [{"term": {"workflow": workflow}}]}
        else:
            q["filter"] = {"and": [{"not": {"in": {"workflow": WORKFLOWS}}}]}

        facets = ['couch_recipient_doc_type', 'direction']
        return es_query(q=q, facets=facets, es_url=ES_URLS['sms'], size=0)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("", sortable=False),
            DataTablesColumn(_("Numbers")),
            DataTablesColumn(_("Mobile Worker Messages")),
            DataTablesColumn(_("Case Messages")),
            DataTablesColumn(_("Incoming")),
            DataTablesColumn(_("Outgoing")),
        )

    @property
    def rows(self):

        def row(rowname, workflow=None):
            facets = self.query_sms(workflow)['facets']
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

            return [rowname, 0, to_users, to_cases, incoming, outgoing]

        rows =  [
            row(_("Keywords"), "workflow_keyword"),
            row(_("Reminders"), "workflow_reminder"),
            row(_("Broadcasts"), "workflow_broadcast"),
            row(_("Unknown")),
        ]

        def total(index):
            return sum([l[index] for l in rows])

        self.total_row = [_("Total"), total(1), total(2), total(3), total(4), total(5)]

        return rows

