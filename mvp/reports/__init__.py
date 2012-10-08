from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin

class MVPIndicatorReport(CustomProjectReport, ProjectReportParametersMixin):
    """
        All MVP Reports with indicators should inherit from this.
    """
    fields = []
    flush_layout = True
    hide_filters = True

    @property
    def indicators(self):
        """

        """
        return NotImplementedError

