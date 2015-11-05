

class ChoiceQueryContext(object):

    def __init__(self, report, report_filter, query=None, limit=20, page=0):
        self.report = report
        self.report_filter = report_filter
        self.query = query
        self.limit = limit
        self.page = page

    @property
    def offset(self):
        return self.page * self.limit
