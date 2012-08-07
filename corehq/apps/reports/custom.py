from StringIO import StringIO
import json
from datetime import datetime
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template.context import RequestContext, Context
from django.template.loader import render_to_string
import pytz
from tastypie.http import HttpBadRequest
from corehq.apps.reports import util
from dimagi.utils.modules import to_function
from tempfile import NamedTemporaryFile
from couchexport.models import Format
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response

# Eventually this should all be merged with the StandardHQReport structure. Someday.
# Too confusing to have this and standard.py be essentially very similar things.

class HQReport(object):
    name = "" # the name of the report, will show up in navigation sidebar
    base_slug = None # (ex: manage, billing, reports)
    slug = "" # report's unique (per base_slug) url slug
    icon = None

    report_partial = None
    dispatcher = 'report_dispatcher'

    # used in StandardHQReport --- should check on how these are used in legacy custom reports
    individual = None # selected mobile worker
    case_type = None # case id
    group = None #group id

    # others
    show_time_notice = False # This report is in <foo> timezone. Current time is <bar>.
    fields = [] # all the report filters
    exportable = False # legacy custom reports export differently from StandardTabularHQReport

    asynchronous = False # to display the "loading..." notification or not. Mostly set to False for custom legacy reports and True for new reports
    template_name = None # the default main template to use for this report (usually a template in the async folder, if we're dealing with the global reports)

    # for async and proper non-async fallback to work
    base_template_name = "reports/report_base.html"
    async_base_template_name = "reports/async/default.html"

    # still somewhat used legacy custom report stuff
    headers = None # new reports should use get_headers() and be a subclass of StandardTabularHQReport
    rows = None # new reports should use get_rows() and be a subclass of StandardTabularHQReport
    datespan = None # legacy custom reports and StandardDateHQReports implement this strangely. TODO

    # to my knowledge, this is legacy/possibly unused from original custom reports iteration, and something smarter should be done here
    title = None # How is this different from name? TODO
    description = "" # where is this ever used / should we use this? TODO
    form = None # reports that actually use the form xmlns grab it from the GET parameter directly. That all seems strange. TODO


    def __init__(self, domain, request, base_context = None):
        base_context = base_context or {}
        if not self.name or not self.slug:
            raise NotImplementedError
        self.domain = domain
        self.request = request

        try:
            self.timezone = util.get_timezone(self.request.couch_user.user_id, domain)
        except AttributeError:
            self.timezone = util.get_timezone(None, domain)

        if not self.rows:
            self.rows = []

        if not self.asynchronous:
            self.async_base_template_name = self.base_template_name

        self.context = base_context
        self.context.update(name = self.name,
                            slug = self.slug,
                            description = self.description,
                            template_name = self.get_template(),
                            exportable = self.exportable,
                            export_path = self.request.get_full_path().replace('/custom/', '/export/'),
                            export_formats = Format.VALID_FORMATS,
                            async_report = self.asynchronous,
                            report_base = self.async_base_template_name
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
        # to my knowledge, this is legacy from original custom reports iteration, and something smarter should be done here
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
            return "reports/async/tabular.html"

    def as_view(self):
        if self.asynchronous:
            from .util import report_context
            self.context.update(report_context(self.domain,
                title = self.name,
                show_time_notice = self.show_time_notice
            ))
        else:
            self.get_report_context()
            self.calc()
            self.base_template_name = self.get_template()
        return render_to_response(self.base_template_name, self.context, context_instance=RequestContext(self.request))

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
            return HttpBadRequest("Export not supported.")
        format = self.request.GET.get('format', None)
        if not format:
            return HttpBadRequest("Please specify a format")

        temp = StringIO()
        export_from_tables(self.context['tables'], temp, format)
        return export_response(temp, format, self.slug)

    def as_async(self, static_only=False):
        process_filters = bool(self.request.GET.get('hq_filters'))
        if static_only:
            self.context.update(dict(original_template=self.get_template()))
            self.template_name = "reports/async/static_only.html"
        if not process_filters:
            self.fields = []
        self.get_report_context()
        self.calc()
        report_template = render_to_string(self.get_template(), self.context, context_instance=RequestContext(self.request))
        filter_template = render_to_string('reports/async/filters.html', self.context, context_instance=RequestContext(self.request)) if process_filters else None
        return HttpResponse(json.dumps(dict(filters=filter_template, report=report_template, title=self.name, slug=self.slug)))

    def as_async_filters(self):
        self.build_selector_form()
        filter_template = render_to_string('reports/async/filters.html', self.context, context_instance=RequestContext(self.request))
        return HttpResponse(json.dumps(dict(filters=filter_template, title=self.name, slug=self.slug)))

    @classmethod
    def get_url(cls, domain):
        return reverse(cls.dispatcher, args=[domain, cls.slug])

    @classmethod
    def show_in_list(cls, domain, user):
        return True

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
        self.context["slug"] = self.slug
        self.update_context()
        return render_to_string(self.template, self.context)

    def update_context(self):
        """
        If your select field needs some context (for example, to set the default) you can set that up here.
        """
        pass

class ReportSelectField(ReportField):
    slug = "generic_select"
    template = "reports/fields/select_generic.html"
    name = "Generic Select"
    default_option = "Select Something..."
    options = [dict(val="val", text="text")]
    cssId = "generic_select_box"
    cssClasses = "span4"
    selected = None
    hide_field = False

    def update_params(self):
        self.selected = self.request.GET.get(self.slug)

    def update_context(self):
        self.update_params()
        self.context['hide_field'] = self.hide_field
        self.context['select'] = dict(
            options=self.options,
            default=self.default_option,
            cssId=self.cssId,
            cssClasses=self.cssClasses,
            label=self.name,
            selected=self.selected
        )

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
    # Don't use. Phase out soon.
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



