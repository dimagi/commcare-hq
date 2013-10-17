from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin, ProjectReport


class TrialConnectReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin, DatespanMixin):
    is_cacheable = True
    emailable = True

    @property
    def base_query(self):
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {
                            'date': {
                                "from": self.datespan.startdate_param_utc,
                                "to": self.datespan.enddate_param_utc,
                                "include_upper": False}}}]}}}
        return self.add_recipients_to_query(q)

    def add_recipients_to_query(self, q):
        recipients = self.cases_by_case_group
        if self.users_by_group:
            recipients.extend(self.combined_user_ids)
        if recipients:
            q["query"]["bool"]["must"].append({"in": {"couch_recipient": recipients}})
        return q
