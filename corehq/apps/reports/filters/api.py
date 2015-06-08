"""
API endpoints for filter options
"""
import logging
from itertools import islice

from django.utils.translation import ugettext as _
from django.views.generic import View

from braces.views import JSONResponseMixin

from corehq.apps.commtrack.models import SQLLocation
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.elastic import es_wrapper, ESError
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception

from corehq.apps.reports.filters.users import EmwfMixin

logger = logging.getLogger(__name__)


class EmwfOptionsView(LoginAndDomainMixin, EmwfMixin, JSONResponseMixin, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    """

    def get(self, request, domain):
        self.domain = domain
        self.q = self.request.GET.get('q', None)
        if self.q and self.q.strip():
            tokens = self.q.split()
            queries = ['%s*' % tokens.pop()] + tokens
            self.user_query = {"bool": {"must": [
                {"query_string": {
                    "query": q,
                    "fields": ["first_name", "last_name", "username"],
                }} for q in queries
            ]}}
            self.group_query = {"bool": {"must": [
                {"query_string": {
                    "query": q,
                    "default_field": "name",
                }} for q in queries
            ]}}
        else:
            self.user_query = None
            self.group_query = None
        try:
            self._init_counts()
            return self.render_json_response({
                'results': self.get_options(),
                'total': self.total_results,
            })
        except ESError as e:
            if self.q:
                # Likely caused by an invalid user query
                # A query that causes this error immediately follows a very
                # similar query that should be caught by the else clause if it
                # errors.  If that error didn't happen, the error was probably
                # introduced by the addition of the query_string query, which
                # contains the user's input.
                logger.info('ElasticSearch error caused by query "%s": %s',
                    self.q, e)
            else:
                # The error was our fault
                notify_exception(request, e)
        return self.render_json_response({
            'results': [],
            'total': 0,
        })

    @property
    def locations_query(self):
        return SQLLocation.objects.filter(
            name__icontains=self.q.lower(),
            domain=self.domain,
        )

    def get_location_groups(self):
        for loc in self.locations_query:
            group = loc.reporting_group_object()
            yield (group._id, group.name + ' [group]')

    def get_locations_size(self):
        return self.locations_query.count()

    def _init_counts(self):
        groups, _ = self.group_es_call(size=0, return_count=True)
        users, _ = self.user_es_call(size=0, return_count=True)
        self.group_start = len(self.user_types)
        self.location_start = self.group_start + groups
        self.user_start = self.location_start + self.get_locations_size()
        self.total_results = self.user_start + users

    def get_options(self):
        page = int(self.request.GET.get('page', 1))
        limit = int(self.request.GET.get('page_limit', 10))
        start = limit * (page - 1)
        stop = start + limit

        options = self.user_types[start:stop]

        g_start = max(0, start - self.group_start)
        g_size = limit - len(options) if start < self.location_start else 0
        options += self.get_groups(g_start, g_size) if g_size else []

        l_start = max(0, start - self.location_start)
        l_size = limit - len(options) if start < self.user_start else 0
        l_end = l_start + l_size
        location_groups = islice(self.get_location_groups(), l_start, l_end)
        options += location_groups

        u_start = max(0, start - self.user_start)
        u_size = limit - len(options)
        options += self.get_users(u_start, u_size) if u_size else []

        return [{'id': id, 'text': text} for id, text in options]

    @property
    @memoized
    def user_types(self):
        return filter(
            lambda user_type: self.q.lower() in user_type[1].lower(),
            super(EmwfOptionsView, self).user_types
        )

    def user_es_call(self, **kwargs):
        return es_wrapper('users', domain=self.domain, q=self.user_query, **kwargs)

    def get_users(self, start, size):
        fields = ['_id', 'username', 'first_name', 'last_name', 'doc_type']
        users = self.user_es_call(fields=fields, start_at=start, size=size,
            sort_by='username.exact', order='asc')
        return [self.user_tuple(u) for u in users]

    def group_es_call(self, **kwargs):
        reporting_filter = {"term": {'reporting': "true"}}
        return es_wrapper('groups', domain=self.domain, q=self.group_query,
                          filters=[reporting_filter], doc_type='Group',
                          **kwargs)

    def get_groups(self, start, size):
        fields = ['_id', 'name']
        groups = self.group_es_call(
            fields=fields,
            sort_by="name.exact",
            order="asc",
            start_at=start,
            size=size,
        )
        return [self.reporting_group_tuple(g) for g in groups]
