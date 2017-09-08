import json

from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.users.analytics import get_search_users_in_domain_es_query


class MessagingRecipientHandler(BaseAsyncHandler):
    slug = 'messaging_recipients'
    allowed_actions = [
        'recipients'
    ]

    @property
    def recipients_response(self):
        domain = self.request.domain
        query = self.data.get('searchString')
        users = get_search_users_in_domain_es_query(domain, query, 10, 0)
        users = users.mobile_users().source(('_id', 'base_username')).run().hits
        ret = [
            {'id': user['_id'], 'text': user['base_username']}
            for user in users
        ]
        return ret

    def _fmt_success(self, data):
        success = json.dumps({'results': data}, cls=LazyEncoder)
        return success
