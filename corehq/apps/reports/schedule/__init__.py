from django.http import HttpRequest
from corehq.apps.reports.schedule.parsers import ReportParser
from corehq.apps.reports.schedule.request import RequestProcessor
from django.template.loader import render_to_string


class ReportSchedule(object):
    """
    A basic report scedule, fully customizable, but requiring you to 
    understand exactly what to pass to the view at runtime.
    """
    
    def __init__(self, view_func, view_args=None, title="unspecified", 
                 processor=RequestProcessor(), auth=None):
        self._view_func = view_func
        if view_args is not None:
            self._view_args = view_args
        else: 
            self._view_args = {}
        self._processor = processor
        self._title = title
        self.auth = auth if auth else (lambda user: True)
    
    @property
    def title(self):
        return self._title
    
    def get_response(self, user, domain):
        # these three lines are a complicated way of saying request.user = user.
        # could simplify if the abstraction doesn't make sense.
        request = HttpRequest()
        self._processor.preprocess(request, user=user.get_django_user(), domain=domain)
        response = self._view_func(request, **self._view_args)
        parser = ReportParser(response.content)
        return render_to_string("reports/report_email.html", { "report_body": parser.get_html(), "domain": domain })

class DomainedReportSchedule(ReportSchedule):
    
    def get_response(self, user, domain):
        self._view_args["domain"] = domain
        return super(DomainedReportSchedule, self).get_response(user, domain)
        
class BasicReportSchedule(object):
    """
    These are compatibile with the daily_submission views
    """
    
    def __init__(self, view_func, couch_view, title):
        self._view_func = view_func
        self._couch_view = couch_view
        self._title = title
        self.auth = lambda user: True
    
    @property
    def title(self):
        return self._title
    
    def get_response(self, user, domain):
        # these three lines are a complicated way of saying request.user = user.
        # could simplify if the abstraction doesn't make sense.
        processor = RequestProcessor()
        request = HttpRequest()
        processor.preprocess(request, user=user.get_django_user())
        response = self._view_func(request, domain, self._couch_view, self._title)
        parser = ReportParser(response.content)
        return render_to_string("reports/report_email.html", { "report_body": parser.get_html(), "domain": domain })
        