from __future__ import absolute_import
import json
from corehq.apps.casegroups.dbaccessors import search_case_groups_in_domain
from corehq.apps.es import GroupES
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.analytics import get_search_users_in_domain_es_query


class MessagingRecipientHandler(BaseAsyncHandler):
    slug = 'scheduling_recipients'
    allowed_actions = [
        'user_recipients',
        'user_group_recipients',
        'user_organization_recipients',
        'case_group_recipients',
    ]

    @property
    def user_recipients_response(self):
        domain = self.request.domain
        query = self.data.get('searchString')
        users = get_search_users_in_domain_es_query(domain, query, 10, 0)
        users = users.mobile_users().source(('_id', 'base_username')).run().hits
        ret = [
            {'id': user['_id'], 'text': user['base_username']}
            for user in users
        ]
        return ret

    @property
    def user_group_recipients_response(self):
        domain = self.request.domain
        query = self.data.get('searchString')
        group_result = (
            GroupES()
            .domain(domain)
            .not_deleted()
            .search_string_query(query, default_fields=['name'])
            .size(10)
            .sort('name')
            .source(('_id', 'name'))
        )
        return [
            {'id': group['_id'], 'text': group['name']}
            for group in group_result.run().hits
        ]

    @property
    def user_organization_recipients_response(self):
        domain = self.request.domain
        query = self.data.get('searchString')
        result = (
            SQLLocation
            .active_objects
            .filter(domain=domain, name__icontains=query)
            .order_by('name')
            .values_list('location_id', 'name')
        )[0:10]
        return [
            {'id': row[0], 'text': row[1]}
            for row in result
        ]

    @property
    def case_group_recipients_response(self):
        domain = self.request.domain
        query = self.data.get('searchString')
        return [
            {'id': result[0], 'text': result[1]}
            for result in search_case_groups_in_domain(domain, query, limit=10)
        ]

    def _fmt_success(self, data):
        success = json.dumps({'results': data}, cls=LazyEncoder)
        return success
