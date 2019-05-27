from __future__ import absolute_import
from __future__ import unicode_literals

import six
import json

from collections import namedtuple
from abc import ABCMeta, abstractmethod

from memoized import memoized

from django.utils.translation import ugettext as _
from django.core.cache import cache

from corehq.apps.reports.v2.exceptions import (
    EndpointNotFoundError,
    ReportFilterNotFound,
)

EndpointContext = namedtuple('EndpointContext', 'slug urlname')
ColumnMeta = namedtuple('ColumnMeta', 'title name width sort')
ReportFilterData = namedtuple('ReportFilterData', 'name value')


class ReportFilterWidget(object):
    SELECT2_MULTI_ASYNC = 'select2-multi-async'
    SELECT2_SINGLE = 'select2-single'


class BaseReport(object):
    """
    This is the glue that ties all the moving parts of a report together.
    """
    slug = None
    data_endpoints = ()
    options_endpoints = ()
    formatters = ()
    columns = []
    column_filters = []
    unsortable_column_names = []
    report_filters = []
    initial_report_filters = []  # list of ReportFilterData

    def __init__(self, request, domain):
        """
        :param request: HttpRequest
        :param domain: String
        """
        self.request = request
        self.domain = domain

    @property
    def has_permission(self):
        """
        Override this property with permissions checks to determine whether
        this report is viewable and the corresponding endpoints are viewable.
        :return: boolean
        """
        return True

    def _get_endpoint(self, endpoint_slug, endpoints):
        slug_to_class = {e.slug: e for e in endpoints}
        try:
            endpoint_class = slug_to_class[endpoint_slug]
            return endpoint_class(self.request, self.domain)
        except (KeyError, NameError):
            raise EndpointNotFoundError(
                _("The report endpoint for {}/{} cannot be found.").format(
                    self.slug, endpoint_slug
                )
            )

    def get_data_endpoint(self, endpoint_slug):
        return self._get_endpoint(endpoint_slug, self.data_endpoints)

    def get_options_endpoint(self, endpoint_slug):
        return self._get_endpoint(endpoint_slug, self.options_endpoints)

    def get_report_filter(self, context):
        filter_name = context['name']
        name_to_class = {f.name: f for f in self.report_filters}
        try:
            filter_class = name_to_class[filter_name]
            return filter_class(self.request, self.domain, context)
        except (KeyError, NameError):
            raise ReportFilterNotFound(
                _("Could not find the report filter '{}'").format(filter_name)
            )

    @property
    def context(self):
        endpoints = []
        endpoints.extend(
            [EndpointContext(e.slug, 'endpoint_data') for e in self.data_endpoints]
        )
        endpoints.extend(
            [EndpointContext(e.slug, 'endpoint_options') for e in self.options_endpoints]
        )
        return {
            'slug': self.slug,
            'endpoints': [e._asdict() for e in endpoints],
            'columns': [c._asdict() for c in self.columns],
            'column_filters': [c.get_context() for c in self.column_filters],
            'unsortable_column_names': self.unsortable_column_names,
            'report_filters': [r.get_context() for r in self.report_filters],
            'initial_report_filters': {r.name: r.value
                                       for r in self.initial_report_filters},
        }


class ReportBreadcrumbsContext(object):
    """
    Generates the template context necessary to render the
    reports/v2/partials/breadcrumbs.html template.
    """

    def __init__(self, report, section_title=None, section_url=None):
        self.section_title = section_title
        self.section_url = section_url
        self.report = report

    @property
    def template_context(self):
        return {
            'breadcrumbs': {
                'section': {
                    'title': self.section_title,
                    'url': self.section_url,
                },
                # todo parent pages?
                'current_page': {
                    'title': self.report.title,
                    'url': self.report.url,
                },
            }
        }


class BaseEndpoint(object):
    slug = None

    def __init__(self, request, domain):
        self.domain = domain
        self.request = request

    @property
    def data(self):
        return self.request.POST

    @property
    @memoized
    def report_context(self):
        return json.loads(self.data.get('reportContext', "{}"))


class BaseOptionsEndpoint(BaseEndpoint):

    def get_response(self):
        raise NotImplementedError("please implement get_response")


class BaseDataEndpoint(BaseEndpoint):

    def get_response(self, query, formatters):
        """
        Override this to return a dict for the response
        :return: {}
        """
        raise NotImplementedError("please implement get_response")


class BaseDataFormatter(object):

    def __init__(self, request, domain, raw_data):
        self.domain = domain
        self.request = request

    def get_context(self):
        """
        Override this to return a dict
        :return: {}
        """
        raise NotImplementedError("please implement get_context")


class BaseFilter(six.with_metaclass(ABCMeta)):

    @classmethod
    @abstractmethod
    def get_context(cls):
        """
        Override this to return a dict
        :return: {}
        """
        raise NotImplementedError("please implement get_context")


class BaseReportFilter(BaseFilter):
    name = None
    title = None
    endpoint_slug = None
    widget = None

    def __init__(self, request, domain, context):
        self.request = request
        self.domain = domain
        self.value = context.get('value')
        self.cache_value(self.value)

    @classmethod
    def _cache_key(cls, request, domain):
        return "{}_{}_initial_val_{}".format(
            request.user.username,
            domain,
            cls.name
        )

    @classmethod
    def initial_value(cls, request, domain):
        return cache.get(cls._cache_key(request, domain))

    def cache_value(self, value):
        cache.set(
            self._cache_key(self.request, self.domain),
            value,
            timeout=1000 * 60 * 60 * 24 * 7,  # 7 day timeout
        )

    @classmethod
    def get_context(cls):
        return {
            'title': cls.title,
            'name': cls.name,
            'endpointSlug': cls.endpoint_slug,
            'widget': cls.widget,
        }

    @abstractmethod
    def get_filtered_query(self, query):
        """
        Returns a filtered query object/
        :param query:
        :return: query object
        """
        raise NotImplementedError("please implement get_filtered_query")
