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

    def get(self, request, domain, all_data=False, share_groups=False):
        self.domain = domain
        self.include_share_groups = share_groups
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
        report_groups, _ = self.group_es_call(group_type="reporting",size=0, return_count=True)
        if self.include_share_groups:
            share_groups, _ = self.group_es_call(group_type="case_sharing",size=0, return_count=True)
            groups = report_groups + share_groups
        else:
            groups = report_groups
        users, _ = self.user_es_call(size=0, return_count=True)
        self.group_start = len(self.user_types)
        self.user_start = self.group_start + groups
        self.total_results = self.user_start + users

    def get_options(self):
        page = int(self.request.GET.get('page', 1))
        limit = int(self.request.GET.get('page_limit', 10))
        start = limit*(page-1)
        stop = start + limit

        options = self.user_types[start:stop]

        g_start = max(0, start - self.group_start)
        g_size = limit - len(options) if start < self.user_start else 0
        options += self.get_groups(g_start, g_size) if g_size else []

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

    def group_es_call(self, group_type="reporting", **kwargs):
        # Valid group_types are "reporting" and "case_sharing"
        return es_wrapper('groups', domain=self.domain, q=self.group_query,
            filters=[{"term": {group_type: "true"}}], doc_type='Group',
            **kwargs)

    def get_groups(self, start, size):
        fields = ['_id', 'name']
        total_reporting_groups, ret_reporting_groups = self.group_es_call(
            group_type="reporting",
            fields=fields,
            sort_by="name.exact",
            order="asc",
            start_at=start,
            size=size,
            return_count=True
        )
        if len(ret_reporting_groups) == size or not self.include_share_groups:
            ret_sharing_groups = []
        else:
            # The page size was not consumed by the reporting groups, so add some
            # sharing groups as well.
            if len(ret_reporting_groups) == 0:
                # The start parameter for the reporting group query was greater
                # than the total unpaginated number of reporting groups.
                share_start = start - total_reporting_groups
            else:
                share_start = 0
            share_size = size - len(ret_reporting_groups)

            ret_sharing_groups = self.group_es_call(
                group_type="case_sharing",
                fields=fields,
                sort_by="name.exact",
                order="asc",
                start_at=share_start,
                size=share_size
            )
        return [self.reporting_group_tuple(g) for g in ret_reporting_groups] + \
               [self.sharing_group_tuple(g) for g in ret_sharing_groups]