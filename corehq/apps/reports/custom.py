from StringIO import StringIO
import json
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template.context import RequestContext, Context
from django.template.loader import render_to_string
import pytz
from corehq.apps.reports import util
from dimagi.utils.modules import to_function
from tempfile import NamedTemporaryFile
from couchexport.models import Format
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response

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
    exportable = False

    def __init__(self, domain, request, base_context = None):
        base_context = base_context or {}
        if not self.name or not self.slug:
            raise NotImplementedError
        self.domain = domain
        self.request = request

        self.timezone = util.get_timezone(self.request.couch_user.user_id, domain)
        print "Timezone for this report ", self.timezone.zone

        if not self.rows:
            self.rows = []
        self.context = base_context
        self.context.update(name = self.name,
                            slug = self.slug,
                            description = self.description,
                            template_name = self.template_name,
                            exportable = self.exportable,
                            export_path = self.request.get_full_path().replace('/custom/', '/export/'),
                            export_formats = Format.VALID_FORMATS
        )

    def build_selector_form(self):
        """
        Get custom field info and use it to construct a set of field form HTML to grab the right inputs.
        """
        if not self.fields: return
        field_classes = []
        for f in self.fields:
            klass = to_function(f)
            field_classes.append(klass(self.request, self.domain, self.timezone))
        self.context['custom_fields'] = [{"field": f.render(), "slug": f.slug} for f in field_classes]

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
        Override this function with something that updates self.context, as needed by your report.
        """
        pass

    def json_data(self):
        """
        Override this function to return a python dict, as needed by your report.
        """
        return {}

    def get_template(self):
        if self.template_name:
            return "%s" % self.template_name
        else:
            return "reports/generic_report.html"

    def as_view(self):
        self.get_report_context()
        self.calc()
        return render_to_response(self.get_template(), self.context, context_instance=RequestContext(self.request))

    def as_json(self):
        self.get_report_context()
        self.calc()
        return HttpResponse(json.dumps(self.json_data()))

    def as_export(self):
        """
        This assumes you have either a set of tables under self.context['tables'], or
        self.context['headers'] and self.context['rows'].

        To turn it on, set exportable=True in your report model.
        """
        self.get_report_context()
        self.calc()
        if (not 'tables' in self.context) and ('headers' in self.context):
            t = [self.context['headers']]
            t.extend(self.context['rows'])
            self.context['tables'] = [[self.name, t]]
        if not 'tables' in self.context:
            return self.as_view()
        format = self.request.GET.get('format', None)
        if not format: return self.as_view()

        temp = StringIO()
        export_from_tables(self.context['tables'], temp, format)
        return export_response(temp, format, self.slug)

class ReportField(object):
    slug = ""
    template = ""
    context = Context()

    def __init__(self, request, domain=None, timezone=pytz.utc):
        self.request = request
        self.domain = domain
        self.timezone = timezone

    def render(self):
        if not self.template: return ""
        self.update_context()
        return render_to_string(self.template, self.context)

    def update_context(self):
        """
        If your select field needs some context (for example, to set the default) you can set that up here.
        """
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

class ExampleInputField(ReportField):
    slug = "example-input"
    template = "reports/fields/example-input-select.html"

    def update_context(self):
        self.context['example_input_default'] = "Some Example Text"

class SampleHQReport(HQReport):
    name = "Sample Report"
    slug = "sample"
    description = "A sample report demonstrating the HQ reports system."
    template_name = "reports/sample-report.html"
    fields = ['corehq.apps.reports.custom.ExampleInputField']

    def calc(self):
        self.context['now_date'] = datetime.now()
        self.context['the_answer'] = 42

        text = self.request.GET.get("example-input", None)
        
        if text:
            self.context['text'] = text
        else:
            self.context['text'] = "You didn't type anything!"



