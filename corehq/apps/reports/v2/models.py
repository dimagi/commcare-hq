from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple

from corehq.apps.reports.v2.exceptions import EndpointNotFoundError


EndpointContext = namedtuple('EndpointContext', 'slug urlname')


class BaseReport(object):
    """
    This is the glue that ties all the moving parts of a report together.
    """
    slug = None
    data_endpoints = ()
    filter_endpoints = ()
    formatters = ()

    def __init__(self, request, domain):
        """
        :param request: HttpRequest
        :param domain: String
        """
        self.request = request
        self.domain = domain

    def _get_endpoint(self, endpoint_slug, endpoints):
        slug_to_class = dict([(e.slug, e) for e in endpoints])
        try:
            endpoint_class = slug_to_class[endpoint_slug]
            return endpoint_class(self.request, self.domain)
        except (KeyError, NameError):
            raise EndpointNotFoundError(
                "The report endpoint for {}/{} cannot be found.".format(
                    self.slug, endpoint_slug
                )
            )

    def get_data_endpoint(self, endpoint_slug):
        return self._get_endpoint(endpoint_slug, self.data_endpoints)

    def get_filters(self):
        for endpoint in self.filter_endpoints:
            yield endpoint(self.request, self.domain)

    @property
    def context(self):
        endpoints = []
        endpoints.extend(
            [EndpointContext(e.slug, 'endpoint_data') for e in self.data_endpoints]
        )
        endpoints.extend(
            [EndpointContext(e.slug, 'endpoint_filter') for e in self.filter_endpoints]
        )
        return {
            'slug': self.slug,
            'endpoints': [e._asdict() for e in endpoints],
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


class BaseFilterEndpoint(BaseEndpoint):

    def get_filtered_query(self, query):
        raise NotImplementedError("please implement get_filtered_query")


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
