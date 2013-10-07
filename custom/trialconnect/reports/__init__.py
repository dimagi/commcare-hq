from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin, CustomProjectReport


class TrialConnectReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
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
                                "from": self.datespan.startdate_param,
                                "to": self.datespan.enddate_param,
                                "include_upper": True}}}]}}}

        if self.users_by_group:
            q["query"]["bool"]["must"].append({"in": {"couch_recipient": self.combined_user_ids}})
        if self.cases_by_case_group:
            q["query"]["bool"]["must"].append({"in": {"couch_recipient": self.cases_by_case_group}})

        return q