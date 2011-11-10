from datetime import datetime
from django.conf import settings
from django.shortcuts import render_to_response
from django.template.context import RequestContext, Context
from django.template.loader import render_to_string
from dimagi.utils.modules import to_function

class HQReport(object):
    name = ""
    slug = ""
    description = ""
    template_name = None
    report_partial = None
    title = None
    headers = None
    rows = None
    individual = None
    case_type = None
    group = None
    form = None,
    datespan = None
    show_time_notice = False
    fields = []

    def __init__(self, domain, request, base_context = {}):
        if not self.name or not self.slug:
            raise NotImplementedError
        self.domain = domain
        self.request = request
        self.rows = []
        self.context = base_context
        self.context.update(name = self.name,
                            slug = self.slug,
                            description = self.description,
                            template_name = self.template_name,
        )

    def build_selector_form(self):
        if not self.fields: return
        field_classes = []
        for f in self.fields:
            klass = to_function(f)
            field_classes.append(klass(self.request))
        tmp_context = {'fields': [f.render() for f in field_classes]}
        self.context['selector'] = render_to_string("reports/partials/selector_form.html", tmp_context)

    def get_report_context(self):
        # circular import
        from .util import report_context
        self.build_selector_form()
        self.context.update(report_context(self.domain,
                                        report_partial = self.report_partial,
                                        title = self.name,
                                        headers = self.headers,
                                        rows = self.rows,
                                        individual = self.individual,
                                        case_type = self.case_type,
                                        group = self.group,
                                        form = None, #self.form,
                                        datespan = self.datespan,
                                        show_time_notice = self.show_time_notice
                                      ))

    def calc(self):
        """
        Override this function with something that updates self.context.
        """
        pass

    def get_template(self):
        if self.template_name:
            return "%s" % self.template_name
        else:
            return "reports/generic_report.html"

    def as_view(self):
        self.get_report_context()
        self.calc()
        return render_to_response(self.get_template(), self.context, context_instance=RequestContext(self.request))

class ReportField(object):
    slug = ""
    template = ""
    context = Context()

    def __init__(self, request):
        self.request = request

    def render(self):
        if not self.template: return ""
        self.update_context()
        return render_to_string(self.template, self.context)

    def update_context(self):
        pass

class MonthField(ReportField):
    slug = "month"
    template = "reports/partials/month-select.html"

    def update_context(self):
        self.context['month'] = self.request.GET.get('month', datetime.utcnow().month)

class YearField(ReportField):
    slug = "year"
    template = "reports/partials/year-select.html"

    def update_context(self):
        year = getattr(settings, 'START_YEAR', 2008)
        self.context['years'] = range(year, datetime.utcnow().year + 1)
        self.context['year'] = int(self.request.GET.get('year', datetime.utcnow().year))

class SampleHQReport(HQReport):
    name = "Sample Report"
    slug = "sample"
    description = "Sample report that just gets a list of users."

    def calc(self):
        pass




