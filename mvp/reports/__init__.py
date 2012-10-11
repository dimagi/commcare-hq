from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin

class MVPIndicatorReport(CustomProjectReport, ProjectReportParametersMixin):
    """
        All MVP Reports with indicators should inherit from this.
    """
    flush_layout = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField']

