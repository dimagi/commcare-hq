"""
API endpoints for filter options
"""
from django.utils.translation import ugettext as _
from django.views.generic import View

from braces.views import JSONResponseMixin

from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.elastic import es_wrapper
from dimagi.utils.decorators.memoized import memoized

from ..models import HQUserType
from ..util import _report_user_dict


def user_tuple(u):
    user = _report_user_dict(u)
    uid = "u__%s" % user['user_id']
    name = "%s [user]" % user['username_in_report'].split('@')[0]
    return (uid, name)


def group_tuple(g):
    return ("g__%s" % g['_id'], "%s [group]" % g['name'])


class EmwfOptionsView(LoginAndDomainMixin, JSONResponseMixin, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    """

    def get(self, request, domain):
        self.domain = domain
        self.q = self.request.GET.get('q', None)
        if self.q:
            tokens = self.q.split(' ')
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
        self._init_counts()
        return self.render_json_response({
            'results': self.get_options(),
            'total': self.total_results,
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
        basics = [("t__0", _("[All mobile workers]"))] + \
            [("t__%s" % (i+1), "[%s]" % name)
                for i, name in enumerate(HQUserType.human_readable[1:])]
        return filter(lambda basic: self.q.lower() in basic[1].lower(), basics)

    def user_es_call(self, **kwargs):
        return es_wrapper('users', domain=self.domain, q=self.user_query, **kwargs)

    def get_users(self, start, size):
        fields = ['_id', 'username', 'first_name', 'last_name']
        users = self.user_es_call(fields=fields, start_at=start, size=size,
            sort_by='username.exact', order='asc')
        return [user_tuple(u) for u in users]

    def group_es_call(self, **kwargs):
        reporting_filter = {"term": {"reporting": "true"}}
        return es_wrapper('groups', domain=self.domain, q=self.group_query,
            doc_type='Group', filters=[reporting_filter], **kwargs)

    def get_groups(self, start, size):
        fields = ['_id', 'name']
        groups = self.group_es_call(fields=fields, sort_by='name.exact',
            order='asc', start_at=start, size=size)
        return [group_tuple(g) for g in groups]
