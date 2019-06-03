"""
API endpoints for filter options
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import logging

from django.views.generic import View

from braces.views import JSONResponseMixin

from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.const import DEFAULT_PAGE_LIMIT
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.elastic import ESError
from memoized import memoized
from dimagi.utils.logging import notify_exception

from corehq.apps.reports.filters.controllers import (
    EmwfOptionsController,
    MobileWorkersOptionsController,
    CaseListFilterOptionsController,
)

from phonelog.models import DeviceReportEntry

logger = logging.getLogger(__name__)


@location_safe
class EmwfOptionsView(LoginAndDomainMixin, JSONResponseMixin, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    """

    @property
    @memoized
    def options_controller(self):
        return EmwfOptionsController(self.request, self.domain, self.search)

    def get(self, request, domain):
        self.domain = domain
        self.search = self.request.GET.get('q', '')

        try:
            count, options = self.options_controller.get_options()
            return self.render_json_response({
                'results': options,
                'total': count,
            })
        except ESError as e:
            if self.search:
                # Likely caused by an invalid user query
                # A query that causes this error immediately follows a very
                # similar query that should be caught by the else clause if it
                # errors.  If that error didn't happen, the error was probably
                # introduced by the addition of the query_string query, which
                # contains the user's input.
                logger.info('ElasticSearch error caused by query "%s": %s',
                            self.search, e)
            else:
                # The error was our fault
                notify_exception(request, e)
        return self.render_json_response({
            'results': [],
            'total': 0,
        })


class MobileWorkersOptionsView(EmwfOptionsView):
    """
    Paginated Options for the Mobile Workers selection tool
    """
    urlname = 'users_select2_options'

    @property
    @memoized
    def options_controller(self):
        return MobileWorkersOptionsController(self.request, self.domain, self.search)

    # This endpoint is used by select2 single option filters
    def post(self, request, domain):
        self.domain = domain
        self.search = self.request.POST.get('q', None)
        try:
            count, options = self.options_controller.get_options()
            return self.render_json_response({
                'items': options,
                'total': count,
                'limit': request.POST.get('page_limit', DEFAULT_PAGE_LIMIT),
                'success': True
            })
        except ESError as e:
            if self.search:
                # Likely caused by an invalid user query
                # A query that causes this error immediately follows a very
                # similar query that should be caught by the else clause if it
                # errors.  If that error didn't happen, the error was probably
                # introduced by the addition of the query_string query, which
                # contains the user's input.
                logger.info('ElasticSearch error caused by query "%s": %s',
                            self.search, e)
            else:
                # The error was our fault
                notify_exception(request, e)
        return self.render_json_response({
            'results': [],
            'total': 0,
        })


@location_safe
class CaseListFilterOptions(EmwfOptionsView):

    @property
    @memoized
    def options_controller(self):
        return CaseListFilterOptionsController(self.request, self.domain, self.search)


@location_safe
class ReassignCaseOptions(CaseListFilterOptions):

    @property
    def data_sources(self):
        """
        Includes case-sharing groups but not reporting groups
        """
        sources = []
        if self.request.can_access_all_locations:
            sources.append((self.get_sharing_groups_size, self.get_sharing_groups))
        sources.append((self.get_locations_size, self.get_locations))
        sources.append((self.get_all_users_size, self.get_all_users))
        return sources



class DeviceLogFilter(LoginAndDomainMixin, JSONResponseMixin, View):
    field = None

    def get(self, request, domain):
        q = self.request.GET.get('q', None)
        field_filter = {self.field + "__startswith": q}
        query_set = (
            DeviceReportEntry.objects
            .filter(domain=domain)
            .filter(**field_filter)
            .distinct(self.field)
            .values_list(self.field, flat=True)
            .order_by(self.field)
        )
        values = query_set[self._offset():self._offset() + self._page_limit() + 1]
        return self.render_json_response({
            'results': [{'id': v, 'text': v} for v in values[:self._page_limit()]],
            'more': len(values) > self._page_limit(),
        })

    def _page_limit(self):
        page_limit = self.request.GET.get("page_limit", DEFAULT_PAGE_LIMIT)
        try:
            return int(page_limit)
        except ValueError:
            return DEFAULT_PAGE_LIMIT

    def _page(self):
        page = self.request.GET.get("page", 1)
        try:
            return int(page)
        except ValueError:
            return 1

    def _offset(self):
        return self._page_limit() * (self._page() - 1)


class DeviceLogUsers(DeviceLogFilter):

    def get(self, request, domain):
        q = self.request.GET.get('q', None)
        users_query = (get_search_users_in_domain_es_query(domain, q, self._page_limit(), self._offset())
            .show_inactive()
            .remove_default_filter("not_deleted")
            .source("username")
        )
        values = [x['username'].split("@")[0] for x in users_query.run().hits]
        count = users_query.count()
        return self.render_json_response({
            'results': [{'id': v, 'text': v} for v in values],
            'total': count,
        })


class DeviceLogIds(DeviceLogFilter):
    field = 'device_id'
