from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin


def div(num, denom, percent=False):
    floater = 100.0 if percent else 1.0
    val = num * floater / denom if denom != 0 else 0
    return "%.2f" % val + ("%" if percent else "")


class CommConnectReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin, DatespanMixin):
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
        if self.users_by_group:
            q["query"]["bool"]["must"].append({"in": {"couch_recipient": self.combined_user_ids}})
        if self.cases_by_case_group:
            q["query"]["bool"]["must"].append({"in": {"couch_recipient": self.cases_by_case_group}})
        return q