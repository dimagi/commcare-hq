from __future__ import absolute_import
import json

from corehq.apps.es import GroupES
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.users.analytics import get_search_users_in_domain_es_query


class MessagingRecipientHandler(BaseAsyncHandler):
    slug = 'scheduling_recipients'
    allowed_actions = [
        'user_recipients',
        'user_group_recipients',
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

    def _fmt_success(self, data):
        success = json.dumps({'results': data}, cls=LazyEncoder)
        return success
