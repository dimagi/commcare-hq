from StringIO import StringIO
import datetime
import re
import pytz
import json

from celery.utils.log import get_task_logger
from django.http import HttpResponse, Http404
from django.template.context import RequestContext
from django.template.loader import render_to_string
from django.shortcuts import render

from corehq.apps.reports.tasks import export_all_rows_task
from corehq.apps.reports.models import ReportConfig
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.users.models import CouchUser
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.view_utils import absolute_reverse
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from dimagi.utils.couch.pagination import DatatablesParams
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function
from dimagi.utils.web import json_request, json_response
from dimagi.utils.parsing import string_to_boolean
from corehq.apps.reports.cache import request_cache
from django.utils.translation import ugettext

CHART_SPAN_MAP = {1: '10', 2: '6', 3: '4', 4: '3', 5: '2', 6: '2'}


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
    name = None  # Human-readable name to be used in the UI
    slug = None  # Name to be used in the URL (with lowercase and underscores)
    section_name = None  # string. ex: "Reports"
    dispatcher = None  # ReportDispatcher subclass

    is_cacheable = False  # whether to use caching on @request_cache methods

    # Code can expect `fields` to be an iterable even when empty (never None)
    fields = ()

    # not required
    description = None  # Human-readable description of the report
    report_template_path = None
    report_partial_path = None

    asynchronous = False
    hide_filters = False
    emailable = False
    printable = False

    exportable = False
    exportable_all = False  # also requires overriding self.get_all_rows
    mobile_enabled = False
    export_format_override = None
    icon = None

    # the defaults for this should be sufficient. But if they aren't, well go for it.
    base_template = None
    base_template_mobile = None
    base_template_async = None
    base_template_filters = None

    flush_layout = False
    # Todo: maybe make these a little cleaner?
    show_timezone_notice = False
    show_time_notice = False
    is_admin_report = False
    special_notice = None
    override_permissions_check = False # whether to ignore the permissions check that's done when rendering the report

    report_title = None
    report_subtitles = []

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        if not self.name or not self.section_name or self.slug is None or not self.dispatcher:
            raise NotImplementedError("Missing a required parameter: (name: %(name)s, section_name: %(section_name)s,"
            " slug: %(slug)s, dispatcher: %(dispatcher)s" % dict(
                name=self.name,
                section_name=self.section_name,
                slug=self.slug,
                dispatcher=self.dispatcher
            ))

        from corehq.apps.reports.dispatcher import ReportDispatcher
        if isinstance(self.dispatcher, ReportDispatcher):
            raise ValueError("Class property dispatcher should point to a subclass of ReportDispatcher.")

        self.request = request
        self.request_params = json_request(self.request.GET if self.request.method == 'GET' else self.request.POST)
        self.domain = domain
        self.context = base_context or {}
        self._update_initial_context()
        self.is_rendered_as_email = False # setting this to true in email_response
        self.override_template = "reports/async/email_report.html"

    def __str__(self):
        return "%(klass)s report named '%(name)s' with slug '%(slug)s' in section '%(section)s'.%(desc)s%(fields)s" % dict(
            klass=self.__class__.__name__,
            name=self.name,
            slug=self.slug,
            section=self.section_name,
            desc="\n   Report Description: %s" % self.description if self.description else "",
            fields="\n   Report Fields: \n     -%s" % "\n     -".join(self.fields) if self.fields else ""
        )

    def __getstate__(self):
        """
            For pickling the report when passing it to Celery.
        """
        logging = get_task_logger(__name__) # logging is likely to happen within celery.
        # pickle only what the report needs from the request object

        request = dict(
            GET=self.request.GET if self.request.method == 'GET' else self.request.POST,
            META=dict(
                QUERY_STRING=self.request.META.get('QUERY_STRING'),
                PATH_INFO=self.request.META.get('PATH_INFO')
            ),
            datespan=self.request.datespan,
            couch_user=None
        )

        try:
            request.update(couch_user=self.request.couch_user.get_id)
        except Exception as e:
            logging.error("Could not pickle the couch_user id from the request object for report %s. Error: %s" %
                          (self.name, e))
        return dict(
            request=request,
            request_params=self.request_params,
            domain=self.domain,
            context={}
        )


    _caching = False
    def __setstate__(self, state):
        """
            For unpickling a pickled report.
        """
        logging = get_task_logger(__name__) # logging lis likely to happen within celery.
        self.domain = state.get('domain')
        self.context = state.get('context', {})

        class FakeHttpRequest(object):
            GET = {}
            META = {}
            couch_user = None
            datespan = None

        request_data = state.get('request')
        request = FakeHttpRequest()
        request.GET = request_data.get('GET', {})
        request.META = request_data.get('META', {})
        request.datespan = request_data.get('datespan')

        try:
            couch_user = CouchUser.get_by_user_id(request_data.get('couch_user'))
            request.couch_user = couch_user
        except Exception as e:
            logging.error("Could not unpickle couch_user from request for report %s. Error: %s" %
                            (self.name, e))
        self.request = request
        self._caching = True
        self.request_params = state.get('request_params')
        self._update_initial_context()

    @property
    @memoized
    def url_root(self):
        path = self.request.META.get('PATH_INFO', "")
        try:
            root = path[0:path.index(self.slug)]
        except ValueError:
            root = None
        return root

    @property
    def queried_path(self):
        path = self.request.META.get('PATH_INFO')
        query = self.request.META.get('QUERY_STRING')
        return "%s:%s" % (path, query)

    @property
    @memoized
    def domain_object(self):
        if self.domain is not None:
            from corehq.apps.domain.models import Domain
            return Domain.get_by_name(self.domain)
        return None

    @property
    @memoized
    def timezone(self):
        if not self.domain:
            return pytz.utc
        else:
            try:
                return get_timezone_for_user(self.request.couch_user, self.domain)
            except AttributeError:
                return get_timezone_for_user(None, self.domain)

    @property
    @memoized
    def template_base(self):
        return self.base_template

    @property
    @memoized
    def mobile_template_base(self):
        return self.base_template_mobile or "reports/mobile/mobile_report_base.html"

    @property
    @memoized
    def template_async_base(self):
        return ((self.base_template_async or "reports/async/default.html")
                                        if self.asynchronous else self.template_base)
    @property
    @memoized
    def template_report(self):
        original_template = self.report_template_path or "reports/async/basic.html"
        if self.is_rendered_as_email:
            self.context.update(original_template=original_template)
            return self.override_template
        return original_template

    @property
    @memoized
    def template_report_partial(self):
        return self.report_partial_path

    @property
    @memoized
    def template_filters(self):
        return self.base_template_filters or "reports/async/filters.html"

    @property
    @memoized
    def rendered_report_title(self):
        return ugettext(self.name)

    @property
    @memoized
    def filter_classes(self):
        filters = []
        fields = self.fields
        for field in fields or []:
            if isinstance(field, basestring):
                klass = to_function(field, failhard=True)
            else:
                klass = field
            filters.append(klass(self.request, self.domain, self.timezone))
        return filters

    @property
    @memoized
    def export_format(self):
        from couchexport.models import Format
        return self.export_format_override or self.request.GET.get('format', Format.XLS_2007)

    @property
    def export_name(self):
        return self.slug

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
        return [
            [
                'table_or_sheet_name',
                [
                    ['header'],
                    ['row 1'],
                    ['row 2'],
                ]
            ]
        ]

    @property
    def filter_set(self):
        """
        Whether a report has any filters set. Based on whether or not there
        is a query string. This gets carried to additional asynchronous calls
        """
        are_filters_set = bool(self.request.META.get('QUERY_STRING'))
        if "filterSet" in self.request.GET:
            try:
                are_filters_set = string_to_boolean(self.request.GET.get("filterSet"))
            except ValueError:
                # not a parseable boolean
                pass
        return are_filters_set


    @property
    def needs_filters(self):
        """
        Whether a report needs filters. A shortcut for hide_filters is false and
        filter_set is false.
        If no filters are used, False is automatically returned.
        """
        if len(self.fields) == 0:
            return False
        else:
            return not self.hide_filters and not self.filter_set

    def _validate_context_dict(self, property):
        if not isinstance(property, dict):
            raise TypeError("property must return a dict")
        return property

    def _update_initial_context(self):
        """
            Intention: Don't override.
        """
        report_configs = ReportConfig.by_domain_and_owner(self.domain,
            self.request.couch_user._id, report_slug=self.slug)
        current_config_id = self.request.GET.get('config_id', '')
        default_config = ReportConfig.default()

        def is_datespan(field):
            field_fn = to_function(field) if isinstance(field, basestring) else field
            return issubclass(field_fn, DatespanFilter)
        has_datespan = any([is_datespan(field) for field in self.fields])

        self.context.update(
            report=dict(
                title=self.rendered_report_title,
                description=self.description,
                section_name=self.section_name,
                slug=self.slug,
                sub_slug=None,
                type=self.dispatcher.prefix,
                url_root=self.url_root,
                is_async=self.asynchronous,
                is_exportable=self.exportable,
                dispatcher=self.dispatcher,
                filter_set=self.filter_set,
                needs_filters=self.needs_filters,
                has_datespan=has_datespan,
                show=(
                    self.override_permissions_check
                    or self.request.couch_user.can_view_reports()
                    or self.request.couch_user.get_viewable_reports()
                ),
                is_emailable=self.emailable,
                is_export_all = self.exportable_all,
                is_printable=self.printable,
                is_admin=self.is_admin_report,   # todo is this necessary???
                special_notice=self.special_notice,
                report_title=self.report_title or self.rendered_report_title,
                report_subtitles=self.report_subtitles,
            ),
            current_config_id=current_config_id,
            default_config=default_config,
            report_configs=report_configs,
            show_time_notice=self.show_time_notice,
            domain=self.domain,
            layout_flush_content=self.flush_layout
        )

    def set_announcements(self):
        """
            Update django messages here.
        """
        pass

    def update_filter_context(self):
        """
            Intention: This probably does not need to be overridden in general.
            Updates the context with filter information.
        """
        self.context.update(report_filters=[dict(
            field=f.render(),
            slug=f.slug) for f in self.filter_classes])

    def update_template_context(self):
        """
            Intention: This probably does not need to be overridden in general.
            Please override template_context instead.
        """
        self.context.update(rendered_as=self.rendered_as)
        self.context['report'].update(
            show_filters=self.fields or not self.hide_filters,
            breadcrumbs=self.breadcrumbs,
            default_url=self.default_report_url,
            url=self.get_url(domain=self.domain),
            title=self.rendered_report_title
        )
        if hasattr(self, 'datespan'):
            self.context.update(datespan=self.datespan)
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
            title=self.rendered_report_title,    # overriding the default title
        )
        self.context.update(self._validate_context_dict(self.report_context))

    @property
    def view_response(self):
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
        self.set_announcements()
        return render(self.request, template, self.context)

    @property
    @request_cache()
    def mobile_response(self):
        """
        This tries to render a mobile version of the report, by just calling
        out to a very simple default template. Likely won't work out of the box
        with most reports.
        """
        if not self.mobile_enabled:
            raise NotImplementedError("This report isn't configured for mobile usage. "
                                      "If you're a developer, add mobile_enabled=True "
                                      "to the report config.")
        async_context = self._async_context()
        self.context.update(async_context)
        return render(self.request, self.mobile_template_base, self.context)

    @property
    def email_response(self):
        """
        This renders a json object containing a pointer to the static html 
        content of the report. It is intended for use by the report scheduler.
        """
        self.is_rendered_as_email = True
        return self.async_response

    @property
    @request_cache()
    def async_response(self):
        """
            Intention: Not to be overridden in general.
            Renders the asynchronous view of the report template, returned as json.
        """
        return HttpResponse(json.dumps(self._async_context()), content_type='application/json')

    def _async_context(self):
        self.update_template_context()
        self.update_report_context()

        rendered_filters = None
        if bool(self.request.GET.get('hq_filters')):
            self.update_filter_context()
            rendered_filters = render_to_string(self.template_filters, self.context,
                context_instance=RequestContext(self.request)
            )
        rendered_report = render_to_string(self.template_report, self.context,
            context_instance=RequestContext(self.request)
        )

        return dict(
            filters=rendered_filters,
            report=rendered_report,
            title=self.rendered_report_title,
            slug=self.slug,
            url_root=self.url_root
        )

    @property
    def excel_response(self):
        file = StringIO()
        export_from_tables(self.export_table, file, self.export_format)
        return file

    @property
    @request_cache(expiry=60 * 10)
    def filters_response(self):
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

    @property
    @request_cache()
    def json_response(self):
        """
            Intention: Not to be overridden in general.
            Renders the json version for the report, if available.
        """
        return json_response(self.json_dict)

    @property
    @request_cache()
    def export_response(self):
        """
        Intention: Not to be overridden in general.
        Returns the tabular export of the data, if available.
        """
        if self.exportable_all:
            export_all_rows_task.delay(self.__class__, self.__getstate__())
            return HttpResponse()
        else:
            temp = StringIO()
            export_from_tables(self.export_table, temp, self.export_format)
            return export_response(temp, self.export_format, self.export_name)

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "reports/async/print_report.html"
        return HttpResponse(self._async_context()['report'])

    @property
    def partial_response(self):
        """
            Use this response for rendering smaller chunks of your report.
            (Great if you have a giant report with annoying, complex indicators.)
        """
        raise Http404

    @classmethod
    def get_url(cls, domain=None, render_as=None, **kwargs):
        # NOTE: I'm pretty sure this doesn't work if you ever pass in render_as
        # but leaving as is for now, as it should be obvious as soon as that 
        # breaks something

        if isinstance(cls, cls):
            domain = getattr(cls, 'domain')
            render_as = getattr(cls, 'rendered_as')
        if render_as is not None and render_as not in cls.dispatcher.allowed_renderings():
            raise ValueError('The render_as parameter is not one of the following allowed values: %s' %
                             ', '.join(cls.dispatcher.allowed_renderings()))
        url_args = [domain] if domain is not None else []
        if render_as is not None:
            url_args.append(render_as+'/')
        return absolute_reverse(cls.dispatcher.name(),
                                args=url_args + [cls.slug])

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return False

    @classmethod
    def get_subpages(cls):
        """
        List of subpages to show in sidebar navigation.
        """
        return []


class GenericTabularReport(GenericReportView):
    """
        Override the following properties:
        @property
        headers
            - returns a DataTablesHeader object

        @property
        rows
            - returns a 2D list of rows.

        ## AJAX pagination
        If you plan on using ajax pagination, take into consideration
        the following properties when rendering self.rows:
        self.pagination.start (skip)
        self.pagination.count (limit)

        Make sure you also override the following properties as necessary:
        @property
        total_records
            - returns an integer
            - the total records of what you are paginating over

        @property
        shared_pagination_GET_params
            - this is where you select the GET parameters to pass to the paginator
            - returns a list formatted like [dict(name='group', value=self.group_id)]

        ## Charts
        To include charts in the report override the following property.
        @property
        charts
            - returns a list of Chart objects e.g. PieChart, MultiBarChart

        You can also adjust the following properties:
        charts_per_row
            - the number of charts to show in a row. 1, 2, 3, 4, or 6
    """
    # new class properties
    total_row = None
    statistics_rows = None
    default_rows = 10
    start_at_row = 0
    show_all_rows = False
    fix_left_col = False
    ajax_pagination = False
    use_datatables = True
    charts_per_row = 1
    bad_request_error_text = None

    # override old class properties
    report_template_path = "reports/async/tabular.html"
    flush_layout = True

    # set to a list of functions that take in a report object 
    # and return a dictionary of items that will show up in 
    # the report context
    extra_context_providers = []

    @property
    def headers(self):
        """
            Override this method to create a functional tabular report.
            Returns a DataTablesHeader() object (or a list, but preferably the former.
        """
        return DataTablesHeader()

    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        return []

    @property
    def get_all_rows(self):
        """
            Override this method to return all records to export
        """
        return []

    @property
    def total_records(self):
        """
            Override for pagination.
            Returns an integer.
        """
        return 0

    @property
    def total_filtered_records(self):
        """
            Override for pagination.
            Returns an integer.
            return -1 if you want total_filtered_records to equal whatever the value of total_records is.
        """
        return -1

    @property
    def charts(self):
        """
            Override to return a list of Chart objects.
        """
        return []

    @property
    def shared_pagination_GET_params(self):
        """
            Override.
            Should return a list of dicts with the name and value of the GET parameters
            that you'd like to pass to the server-side pagination.
            ex: [dict(name='group', value=self.group_id)]
        """
        return []

    @property
    def pagination_source(self):
        return self.get_url(domain=self.domain, render_as='json')

    _pagination = None
    @property
    def pagination(self):
        if self._pagination is None and hasattr(self.request, 'REQUEST'):
            self._pagination = DatatablesParams.from_request_dict(self.request.REQUEST)
        return self._pagination

    @property
    def json_dict(self):
        """
            When you implement self.rows for a paginated report,
            it should take into consideration the following:
            self.pagination.start (skip)
            self.pagination.count (limit)
        """
        rows = list(self.rows)
        total_records = self.total_records
        if not isinstance(total_records, int):
            raise ValueError("Property 'total_records' should return an int.")
        total_filtered_records = self.total_filtered_records
        if not isinstance(total_filtered_records, int):
            raise ValueError("Property 'total_filtered_records' should return an int.")
        ret = dict(
            sEcho=self.pagination.echo,
            iTotalRecords=total_records,
            iTotalDisplayRecords=total_filtered_records if total_filtered_records >= 0 else total_records,
            aaData=rows,
        )

        if self.total_row:
            ret["total_row"] = list(self.total_row)
        if self.statistics_rows:
            ret["statistics_rows"] = list(self.statistics_rows)

        return ret

    @property
    def fixed_cols_spec(self):
        """
            Override
            Returns a dict formatted like:
            dict(num=<num_cols_to_fix>, width=<width_of_total_fixed_cols>)
        """
        return dict(num=1, width=200)

    @staticmethod
    def _strip_tags(value):
        """
        Strip HTML tags from a value
        """
        # Uses regex. Regex is much faster than using an HTML parser, but will
        # strip "<2 && 3>" from a value like "1<2 && 3>2". A parser will treat
        # each cell like an HTML document, which might be overkill, but if
        # using regex breaks values then we should use a parser instead, and
        # take the knock. Assuming we won't have values with angle brackets,
        # using regex for now.
        if isinstance(value, basestring):
            return re.sub('<[^>]*?>', '', value)
        return value

    @property
    def override_export_sheet_name(self):
        """
            Override the export sheet name here. Return a string.
        """
        return None

    _export_sheet_name = None
    @property
    def export_sheet_name(self):
        if self._export_sheet_name is None:
            override = self.override_export_sheet_name
            self._export_sheet_name = override if isinstance(override, str) else self.name # unicode?
        return self._export_sheet_name

    @property
    def export_table(self):
        """
        Exports the report as excel.

        When rendering a complex cell, it will assign a value in the following order:
        1. cell['raw']
        2. cell['sort_key']
        3. str(cell)
        """
        headers = self.headers

        def _unformat_row(row):
            def _unformat_val(val):
                if isinstance(val, dict):
                    return val.get('raw', val.get('sort_key', val))
                return self._strip_tags(val)

            return [_unformat_val(val) for val in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in self.export_rows]
        table.extend(rows)
        if self.total_row:
            table.append(_unformat_row(self.total_row))
        if self.statistics_rows:
            table.extend([_unformat_row(row) for row in self.statistics_rows])

        return [[self.export_sheet_name, table]]

    @property
    def export_rows(self):
        """
        The rows that will be used in an export. Useful if you want to apply any additional
        custom formatting to mirror something that would be done in a template.
        """
        if self.exportable_all:
            return self.get_all_rows
        else:
            return self.rows

    @property
    @request_cache()
    def report_context(self):
        """
            Don't override.
            Override the properties headers and rows instead of this.
        """
        headers = self.headers # not all headers have been memoized
        assert isinstance(headers, (DataTablesHeader, list))
        if isinstance(headers, list):
            raise DeprecationWarning("Property 'headers' should be a DataTablesHeader object, not a list.")

        if self.ajax_pagination and self.is_rendered_as_email:
            rows = self.get_all_rows
            charts = []
        elif self.ajax_pagination or self.needs_filters:
            rows = []
            charts = []
        else:
            rows = list(self.rows)
            charts = list(self.charts)

        if self.total_row is not None:
            self.total_row = list(self.total_row)
        if self.statistics_rows is not None:
            self.statistics_rows = list(self.statistics_rows)

        pagination_spec = dict(is_on=self.ajax_pagination and not self.is_rendered_as_email)
        if self.ajax_pagination:
            shared_params = list(self.shared_pagination_GET_params)
            pagination_spec.update(
                params=shared_params,
                source=self.pagination_source,
                filter=False
            )

        left_col = dict(is_fixed=self.fix_left_col)
        if self.fix_left_col:
            spec = dict(self.fixed_cols_spec)
            left_col.update(fixed=spec)

        context = dict(
            report_table=dict(
                headers=headers,
                rows=rows,
                total_row=self.total_row,
                statistics_rows=self.statistics_rows,
                default_rows=self.default_rows,
                start_at_row=self.start_at_row,
                show_all_rows=self.show_all_rows,
                pagination=pagination_spec,
                left_col=left_col,
                datatables=self.use_datatables,
                bad_request_error_text=self.bad_request_error_text
            ),
            charts=charts,
            chart_span=CHART_SPAN_MAP[self.charts_per_row]
        )
        for provider_function in self.extra_context_providers:
            context.update(provider_function(self))
        return context

    def table_cell(self, value, html=None, zerostyle=False):
        styled_value = '<span class="muted">0</span>' if zerostyle and value == 0 else value
        return dict(
            sort_key=value,
            html="%s" % styled_value if html is None else html
        )


def summary_context(report):
    # will intentionally break if used with something that doesn't have
    # a summary_values attribute
    return {"summary_values": report.summary_values}

class SummaryTablularReport(GenericTabularReport):
    report_template_path = "reports/async/summary_tabular.html"
    extra_context_providers = [summary_context]

    @property
    def data(self):
        """
        Should return a list of data values, that corresponds to the
        headers.
        """
        raise NotImplementedError("Override this function!")

    @property
    def rows(self):
        # for backwards compatibility / easy switching with a single-row table
        return [self.data]

    @property
    def summary_values(self):
        headers = list(self.headers)
        assert (len(self.data) == len(headers))
        return zip(headers, self.data)

class ProjectInspectionReportParamsMixin(object):
    @property
    def shared_pagination_GET_params(self):
        # This was moved from ProjectInspectionReport so that it could be included in CaseReassignmentInterface too
        # I tried a number of other inheritance schemes, but none of them worked because of the already
        # complicated multiple-inheritance chain
        # todo: group this kind of stuff with the field object in a comprehensive field refactor

        return [dict(name='individual', value=self.individual),
                dict(name='group', value=self.group_id),
                dict(name='case_type', value=self.case_type),
                dict(name='ufilter', value=[f.type for f in self.user_filter if f.show])]


class PaginatedReportMixin(object):
    default_sort = None

    def get_sorting_block(self):
        res = []
        #the NUMBER of cols sorting
        sort_cols = int(self.request.GET.get('iSortingCols', 0))
        if sort_cols > 0:
            for x in range(sort_cols):
                col_key = 'iSortCol_%d' % x
                sort_dir = self.request.GET['sSortDir_%d' % x]
                col_id = int(self.request.GET[col_key])
                col = self.headers.header[col_id]
                if col.prop_name is not None:
                    sort_dict = {col.prop_name: sort_dir}
                    res.append(sort_dict)
        if len(res) == 0 and self.default_sort is not None:
            res.append(self.default_sort)
        return res

class ElasticTabularReport(GenericTabularReport, PaginatedReportMixin):
    """
    Tabular report that provides framework for doing elasticsearch backed tabular reports.

    Main thing of interest is that you need es_results to hit ES, and that your datatable headers
    must use prop_name kwarg to enable column sorting.
    """

    @property
    def es_results(self):
        """
        Main meat - run your ES query and return the raw results here.
        """
        raise NotImplementedError("ES Query not implemented")

    @property
    def total_records(self):
        """
            Override for pagination slice from ES
            Returns an integer.
        """
        res = self.es_results
        if res is not None:
            return res['hits'].get('total', 0)
        else:
            return 0


class GetParamsMixin(object):
    @property
    def shared_pagination_GET_params(self):
        """
        Override the params and applies all the params of the originating view to the GET
        so as to get sorting working correctly with the context of the GET params
        """
        ret = super(GetParamsMixin, self).shared_pagination_GET_params
        for k, v in self.request.GET.iterlists():
            ret.append(dict(name=k, value=v))
        return ret


class ElasticProjectInspectionReport(GetParamsMixin, ProjectInspectionReportParamsMixin, ElasticTabularReport):
    pass
