from datetime import datetime

from django.http import HttpResponse
from django.views.generic import View

from braces.views import JSONResponseMixin
from dimagi.utils.dates import DateSpan

from .api import ReportDataSource
from .filters.dates import DatespanFilter


class TestFilter(object):
    def __init__(self, params):
        self.params = params

    @property
    def value(self):
        dict = self.params
        def date_or_nothing(param):
            return datetime.strptime(dict[param], "%Y-%m-%d")\
                        if param in dict and dict[param] else None
        try:
            startdate = date_or_nothing('startdate')
            enddate = date_or_nothing('enddate')
        except ValueError, e:
            return None
        if startdate or enddate:
            return DateSpan(startdate, enddate)
        else:
            return self.default_value

    @property
    def default_value(self):
        return


class TestReportData(ReportDataSource):
    filters = {
        'datespan': TestFilter
    }

    def get_data(self):
        return {
            "startdate": self.report_context['datespan'].value.startdate_param
        }


class TestReport(JSONResponseMixin, View):
    data_model = TestReportData

    def dispatch(self, request, **kwargs):
        return super(TestReport, self).dispatch(request, **kwargs)

    def has_permissions(self, domain, user):
        return True

    def get(self, request, **kwargs):
        report = self.get_json()
        return self.render_json_response(report)

    def get_json(self):
        filter_params = self.request.GET.dict()
        # get a dict of params in some way
        self.data = self.data_model(filter_params)
        return self.data.get_data()

    def _get_initial(self, request, **kwargs):
        pass

    def reverse(self, params):
        return "#"
