from StringIO import StringIO
import datetime
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.template.context import RequestContext
import json
from django.template.loader import render_to_string
import pytz
from corehq.apps.reports import util
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from dimagi.utils.modules import to_function
from dimagi.utils.web import render_to_response, json_request

class GenericReportView(object):
    """
        A generic report structure for viewing a report
        (or pages that follow the reporting structure closely---though that seems a bit hacky)

        This object is handled by the ReportDispatcher and served as a django view based on
        the report maps specified in settings.py

        To make the report return anything, override any or all of the following properties:

        @property
        template_context
            - returns a dict to be inserted into self.context
            - only items relevant to base_template structure should be placed here. Anything
                related to report data and async templates should be done in report_context

        @property
        report_context
            - returns a dict to be inserted into self.context
            - this is where the main processing of the report data should happen
            - can be cached using @cache_report decorator in memcached where you please

        Note: In general you should not be inserting things into self.context directly, unless absolutely
            necessary. Please use the structure in the above properties for updating self.context
            in the relevant places.

        @property
        json_dict
            - returns a dict to be parsed and returned as json for the json version of this report
                (generally has only been useful for datatables paginated reports)

        @property
        export_table
            - returns a multi-dimensional list formatted as export_from_tables would expect:
                [ ['table_or_sheet_name', [['header'] ,['row']] ] ]


    """
    # required to create a report based on this
    name = None         # string. the name of the report that shows up in the heading and the
    section_name = None # string. ex: "Reports"
    slug = None         # string. the report_slug_in_the_url
    # todo: find instances of base_slug and replace with section_slug

    # not required
    asynchronous = False
    hide_filters = False
    exportable = False
    export_format_override = None
    description = None  # string. description of the report. Currently not being used.
    icon = None
    templates = dict(
        base=None,
        base_async=None,
        report=None,
        report_partial=None,
        filters=None
    )

    dispatcher = "report_dispatcher"

    flush_layout = False
    # Todo: maybe make these a little cleaner?
    show_timezone_notice = False
    show_time_notice = False
    is_admin_report = False

    def __init__(self, request, domain=None, base_context=None):
        if not self.name or not self.section_name or not self.slug:
            raise NotImplementedError
        self.request = request
        self.request_params = json_request(self.request.GET)
        self.domain = domain
        self.context = base_context or {}
        self.context.update(
            report=dict(
                title=self.name,
                description=self.description,
                section_name=self.section_name,
                slug=self.slug,
                url_root=self.url_root,
                is_async=self.asynchronous,
                is_admin=self.is_admin_report
            ),
            show_time_notice=self.show_time_notice,
            domain=self.domain
        )

    _url_root = None
    @property
    def url_root(self):
        if self._url_root is None:
            path = self.request.META.get('PATH_INFO', "")
            try:
                root = path[0:path.index(self.slug)]
            except ValueError:
                root = None
            self._url_root = root
        return self._url_root

    _domain_object = None
    @property
    def domain_object(self):
        if self._domain_object is None and self.domain is not None:
            from corehq.apps.domain.models import Domain
            self._domain_object = Domain.get_by_name(self.domain)
        return self._domain_object

    _timezone = None
    @property
    def timezone(self):
        if self._timezone is None:
            if not self.domain:
                self._timezone = pytz.utc
            else:
                try:
                    self._timezone = util.get_timezone(self.request.couch_user.user_id, self.domain)
                except AttributeError:
                    self._timezone = util.get_timezone(None, self.domain)
        return self._timezone

    _template_base = None
    @property
    def template_base(self):
        if self._template_base is None:
            self._template_base = self.templates.get('base') or "%s/base_template.html" % self.section_name
        return self._template_base

    _template_async_base = None
    @property
    def template_async_base(self):
        if self._template_async_base is None:
            self._template_async_base = (self.templates.get('base_async') or "reports/async/default.html") \
                                        if self.asynchronous else self.template_base
        return self._template_async_base

    _template_report = None
    @property
    def template_report(self):
        if self._template_report is None:
            self._template_report = self.templates.get('report') or "reports/async/basic.html"
        return self._template_report

    _template_report_partial = None
    @property
    def template_report_partial(self):
        if self._template_report_partial is None:
            self._template_report_partial = self.templates.get('report_partial') or None
        return self._template_report_partial

    _template_filters = None
    @property
    def template_filters(self):
        if self._template_filters is None:
            self._template_filters = self.templates.get('filters') or "reports/async/filters.html"
        return self._template_filters

    _rendered_report_title = None
    @property
    def rendered_report_title(self):
        """
            Override this to do special report titles that include specific info from the report (ex: a username).
            Inserted into the template as the report title upon rending the report asynchronously or when
            self.asynchronous is false
        """
        if self._rendered_report_title is None:
            self._rendered_report_title = self.name
        return self._rendered_report_title

    _filter_fields = None
    @property
    def filter_fields(self):
        """
            Returns a list of filters for the report.
        """
        if self._filter_fields is None:
            self._filter_fields = []
        return self._filter_fields

    _filter_classes = None
    @property
    def filter_classes(self):
        if self._filter_classes is None:
            filters = []
            for field in self.filter_fields:
                klass = to_function(field)
                filters.append(klass(self.request, self.domain, self.timezone))
            self._filter_classes = filters
        return self._filter_classes

    _export_format = None
    @property
    def export_format(self):
        if self._export_format is None:
            from couchexport.models import Format
            self._export_format = self.export_format_override or self.request.GET.get('format', Format.XLS)
        return self._export_format

    _export_name = None
    @property
    def export_name(self):
        """
            Override this if you don't want <slug>.xls or <slug>.csv to be the tabular export filename.
        """
        if self._export_name is None:
            self._export_name = self.slug
        return self._export_name

    @property
    def default_report_url(self):
        return "#"

    @property
    def breadcrumbs(self):
        """
            Override this for custom breadcrumbs.
            Use the format:
            dict(
                title="breadcrumb title",
                link="url title links to"
            )
            This breadcrumb does not include the report title, it's only the links in between the section name
            and the report title.
        """
        return None

    @property
    def template_context(self):
        """
            Intention: Override if necessary.
            Update context specific to the wrapping template here.
            Nothing specific to the report should go here, use report_context for that.
            Must return a dict.
        """
        return dict()

    @property
    def report_context(self):
        """
            Intention: Override
            !!! CRUCIAL: This is where ALL the intense processing of the report data happens.

            DO NOT update self.context from here or anything that gets processed in here.
            The dictionary returned by this function can get cached in memcached to optimize a report.
            Must return a dict.
        """
        return dict()

    @property
    def json_dict(self):
        """
            Intention: Override
            Return a json-parsable dict, as needed by your report.
        """
        return {}

    @property
    def export_table(self):
        """
            Intention: Override
            Returns an export table to be parsed by export_from_tables.
        """
        return [ ['table_or_sheet_name', [['header'] ,['row']] ] ]

    def _validate_context_dict(self, property):
        if not isinstance(property, dict):
            raise TypeError("property must return a dict")
        return property

    def update_filter_context(self):
        """
            Intention: This probably does not need to be overridden in general.
            Updates the context with filter information.
        """
        self.context.update(report_filters=self.filter_classes)

    def update_template_context(self):
        """
            Intention: This probably does not need to be overridden in general.
            Please override template_context instead.
        """
        self.context['report'].update(
            hide_filters=not self.filter_fields or self.hide_filters,
            breadcrumbs=self.breadcrumbs
        )
        if self.show_timezone_notice:
            self.context.update(timezone=dict(
                    now=datetime.datetime.now(tz=self.timezone),
                    zone=self.timezone.zone
                ))
        self.context.update(self._validate_context_dict(self.template_context))

    def update_report_context(self):
        """
            Intention: This probably does not need to be overridden in general.
            Please override report_context instead.
        """
        self.context.update(
            report_partial=self.template_report_partial,
            report_base=self.template_async_base
        )
        self.context['report'].update(
            title=self.rendered_report_title    # overriding the default title
        )
        self.context.update(self._validate_context_dict(self.report_context))

    def render_view_response(self):
        """
            Intention: Not to be overridden in general.
            Renders the general view of the report template.
        """
        self.update_template_context()
        template = self.template_base
        if not self.asynchronous:
            self.update_filter_context()
            self.update_report_context()
            template = self.template_report
        return render_to_response(template, self.context,
            context_instance=RequestContext(self.request)
        )

    def render_async_response(self, static_only=False):
        """
            Intention: Not to be overridden in general.
            Renders the asynchronous view of the report template, returned as json.
            Note: static_only is True renders _only_ the static html content of the report. It is intended for
                    use by the report scheduler.
        """
        self.update_template_context()
        self.update_report_context()

        template = self.template_base
        if static_only:
            self.context.update(original_template=template)
            template = "reports/async/static_only.html"

        rendered_filters = None
        if bool(self.request.GET.get('hq_filters')):
            self.update_filter_context()
            rendered_filters = render_to_string(self.template_filters, self.context,
                context_instance=RequestContext(self.request)
            )

        rendered_report = render_to_string(template, self.context,
            context_instance=RequestContext(self.request)
        )

        return HttpResponse(json.dumps(dict(
            filters=rendered_filters,
            report=rendered_report,
            title=self.rendered_report_title,
            slug=self.slug,
            url_root=self.url_root
        )))

    def render_filter_only_response(self):
        """
            Intention: Not to be overridden in general.
            Renders just the filters for the report to be fetched asynchronously.
        """
        self.update_filter_context()
        rendered_filters = render_to_string(self.template_filters, self.context,
            context_instance=RequestContext(self.request)
        )
        return HttpResponse(json.dumps(dict(
            filters=rendered_filters,
            slug=self.slug,
            url_root=self.url_root
        )))

    def render_json_response(self):
        """
            Intention: Not to be overridden in general.
            Renders the json version for the report, if available.
        """
        return HttpResponse(json.dumps(self.json_dict))

    def render_export_table_response(self):
        """
            Intention: Not to be overridden in general.
            Returns the tabular export of the data, if available.
        """
        temp = StringIO()
        export_from_tables(self.export_table, temp, self.export_format)
        return export_response(temp, self.export_format, self.export_name)

    @classmethod
    def get_url(cls, *args, **kwargs):
        reverse_args = [args[i] for i in args]
        return reverse(cls.dispatcher, args=reverse_args+[cls.slug])

    @classmethod
    def show_in_list(cls, **kwargs):
        return True