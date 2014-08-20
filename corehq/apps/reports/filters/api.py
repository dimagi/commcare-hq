"""
API endpoints for filter options
"""
import logging

from django.utils.translation import ugettext as _
from django.views.generic import View

from braces.views import JSONResponseMixin

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

    def get(self, request, domain, all_data=False):
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

    def _init_counts(self):
        groups, _ = self.group_es_call(size=0, return_count=True)
        users, _ = self.user_es_call(size=0, return_count=True)
        self.group_start = len(self.basics)
        self.user_start = self.group_start + groups
        self.total_results = self.user_start + users

    def get_options(self):
        page = int(self.request.GET.get('page', 1))
        limit = int(self.request.GET.get('page_limit', 10))
        start = limit*(page-1)
        stop = start + limit

        options = self.basics[start:stop]

        g_start = max(0, start - self.group_start)
        g_size = limit - len(options) if start < self.user_start else 0
        options += self.get_groups(g_start, g_size) if g_size else []

        u_start = max(0, start - self.user_start)
        u_size = limit - len(options)
        options += self.get_users(u_start, u_size) if u_size else []

        return [{'id': id, 'text': text} for id, text in options]

    @property
    @memoized
    def basics(self):
        return filter(
            lambda basic: self.q.lower() in basic[1].lower(),
            super(EmwfOptionsView, self).basics
        )

    def user_es_call(self, **kwargs):
        return es_wrapper('users', domain=self.domain, q=self.user_query, **kwargs)

    def get_users(self, start, size):
        fields = ['_id', 'username', 'first_name', 'last_name', 'doc_type']
        users = self.user_es_call(fields=fields, start_at=start, size=size,
            sort_by='username.exact', order='asc')
        return [self.user_tuple(u) for u in users]

    def group_es_call(self, **kwargs):
        reporting_filter = {"term": {"reporting": "true"}}
        return es_wrapper('groups', domain=self.domain, q=self.group_query,
            doc_type='Group', filters=[reporting_filter], **kwargs)

    def get_groups(self, start, size):
        fields = ['_id', 'name']
        groups = self.group_es_call(fields=fields, sort_by='name.exact',
            order='asc', start_at=start, size=size)
        return [self.group_tuple(g) for g in groups]
