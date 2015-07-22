"""
API endpoints for filter options
"""
import logging

from django.views.generic import View

from braces.views import JSONResponseMixin

from corehq.apps.commtrack.models import SQLLocation
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.elastic import es_wrapper, ESError
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception

from corehq.apps.reports.filters.users import EmwfUtils

logger = logging.getLogger(__name__)


class EmwfOptionsView(LoginAndDomainMixin, JSONResponseMixin, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    """
    @property
    @memoized
    def utils(self):
        return EmwfUtils(self.domain)

    def get(self, request, domain):
        self.domain = domain
        self.q = self.request.GET.get('q', None)
        try:
            count, options = self.get_options()
            return self.render_json_response({
                'results': options,
                'total': count,
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

    def get_locations_query(self, query):
        return SQLLocation.objects.filter(
            name__icontains=query.lower(),
            domain=self.domain,
        )

    def get_locations(self, query, start, size):
        for loc in self.get_locations_query(query)[start:size]:
            group = loc.reporting_group_object()
            yield self.utils.location_group_tuple(group)

    def get_locations_size(self, query):
        return self.get_locations_query(query).count()

    @property
    def data_sources(self):
        return [
            (self.get_static_options_size, self.get_static_options),
            (self.get_groups_size, self.get_groups),
            (self.get_locations_size, self.get_locations),
            (self.get_users_size, self.get_users),
        ]

    def get_options(self):
        page = int(self.request.GET.get('page', 1))
        size = int(self.request.GET.get('page_limit', 10))
        start = size * (page - 1)
        count, options = paginate_options(self.data_sources, self.q, start, size)
        return count, [{'id': id_, 'text': text} for id_, text in options]

    def get_static_options_size(self, query):
        return len(self.get_all_static_options(query))

    def get_all_static_options(self, query):
        return [user_type for user_type in self.utils.static_options
                if query.lower() in user_type[1].lower()]

    def get_static_options(self, query, start, size):
        return self.get_all_static_options(query)[start:start+size]

    def get_es_query_strings(self, query):
        if query and query.strip():
            tokens = query.split()
            return ['%s*' % tokens.pop()] + tokens

    def user_es_call(self, query, **kwargs):
        query = {"bool": {"must": [
            {"query_string": {
                "query": q,
                "fields": ["first_name", "last_name", "username"],
            }} for q in self.get_es_query_strings(query)
        ]}} if query and query.strip() else None
        return es_wrapper('users', domain=self.domain, q=query, **kwargs)

    def get_users_size(self, query):
        return self.user_es_call(query, size=0, return_count=True)[0]

    def get_users(self, query, start, size):
        fields = ['_id', 'username', 'first_name', 'last_name', 'doc_type']
        users = self.user_es_call(query, fields=fields, start_at=start, size=size,
                                  sort_by='username.exact', order='asc')
        return [self.utils.user_tuple(u) for u in users]

    def get_groups_size(self, query):
        return self.group_es_call(query, size=0, return_count=True)[0]

    def group_es_call(self, query, group_type="reporting", **kwargs):
        query = {"bool": {"must": [
            {"query_string": {
                "query": q,
                "default_field": "name",
            }} for q in self.get_es_query_strings(query)
        ]}} if query and query.strip() else None
        type_filter = {"term": {group_type: "true"}}
        return es_wrapper('groups', domain=self.domain, q=query,
                          filters=[type_filter], doc_type='Group',
                          **kwargs)

    def get_groups(self, query, start, size):
        fields = ['_id', 'name']
        groups = self.group_es_call(
            query,
            fields=fields,
            sort_by="name.exact",
            order="asc",
            start_at=start,
            size=size,
        )
        return [self.utils.reporting_group_tuple(g) for g in groups]


def paginate_options(data_sources, query, start, size):
    """
    Returns the appropriate slice of values from the data sources
    data_sources is a list of (count_fn, getter_fn) tuples
        count_fn returns the total number of entries in a data source,
        getter_fn takes in a start and size parameter and returns entries
    """
    # Note this is pretty confusing, check TestEmwfPagination for reference
    options = []
    total = 0
    for get_size, get_objects in data_sources:
        count = get_size(query)
        total += count

        if start > count:  # skip over this whole data source
            start -= count
            continue

        # return a page of objects
        objects = list(get_objects(query, start, size))
        start = 0
        size -= len(objects)  # how many more do we need for this page?
        options.extend(objects)
    return total, options
