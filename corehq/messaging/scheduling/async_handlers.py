from __future__ import absolute_import
import json
from corehq.apps.casegroups.dbaccessors import search_case_groups_in_domain
from corehq.apps.es import GroupES
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from django.utils.translation import ugettext as _


class MessagingRecipientHandler(BaseAsyncHandler):
    slug = 'scheduling_recipients'
    allowed_actions = [
        'schedule_user_recipients',
        'schedule_user_group_recipients',
        'schedule_user_organization_recipients',
        'schedule_case_group_recipients',
    ]

    @property
    def schedule_user_recipients_response(self):
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
    def schedule_user_group_recipients_response(self):
        return self._get_user_group_response()

    def _get_user_group_response(self, case_sharing_only=False):
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
        if case_sharing_only:
            group_result = group_result.is_case_sharing()
        return [
            {'id': group['_id'], 'text': group['name']}
            for group in group_result.run().hits
        ]

    @property
    def schedule_user_organization_recipients_response(self):
        return self._get_user_organization_response()

    def _get_user_organization_response(self, case_sharing_only=False):
        domain = self.request.domain
        query = self.data.get('searchString')
        result = (
            SQLLocation
            .active_objects
            .filter(domain=domain, name__icontains=query)
            .order_by('name')
            .values_list('location_id', 'name')
        )

        if case_sharing_only:
            result = result.filter(location_type__shares_cases=True)

        return [
            {'id': row[0], 'text': row[1]}
            for row in result[:10]
        ]

    @property
    def schedule_case_group_recipients_response(self):
        domain = self.request.domain
        query = self.data.get('searchString')
        return [
            {'id': result[0], 'text': result[1]}
            for result in search_case_groups_in_domain(domain, query, limit=10)
        ]

    def _fmt_success(self, data):
        success = json.dumps({'results': data}, cls=LazyEncoder)
        return success


class SMSSettingsAsyncHandler(MessagingRecipientHandler):
    slug = 'sms_settings_async'

    allowed_actions = [
        'sms_case_registration_user_id',
        'sms_case_registration_owner_id',
    ]

    @property
    def sms_case_registration_user_id_response(self):
        return self.schedule_user_recipients_response

    @property
    def sms_case_registration_owner_id_response(self):
        users = self.schedule_user_recipients_response
        groups = self._get_user_group_response(case_sharing_only=True)
        locations = self._get_user_organization_response(case_sharing_only=True)

        result = (
            [
                {
                    'id': u['id'],
                    'text': _("User: {}").format(u['text']),
                } for u in users
            ] +
            [
                {
                    'id': g['id'],
                    'text': _("User Group: {}").format(g['text']),
                } for g in groups
            ] +
            [
                {
                    'id': l['id'],
                    'text': _("Organization: {}").format(l['text']),
                } for l in locations
            ]
        )

        return result[:10]
