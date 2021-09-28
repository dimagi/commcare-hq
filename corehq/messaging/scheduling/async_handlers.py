import json
from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain, get_latest_released_app
from corehq.apps.app_manager.models import AdvancedForm
from corehq.apps.casegroups.dbaccessors import search_case_groups_in_domain
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.locations.models import LocationType
from corehq.apps.reminders.util import get_combined_id
from corehq.apps.reports.analytics.esaccessors import get_groups_by_querystring
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.util.quickcache import quickcache
from django.utils.translation import ugettext as _


@quickcache(['domain', 'timestamp'], timeout=10 * 60)
def get_visit_scheduler_forms(domain, timestamp):
    """
    The timestamp is set once at the beginning of each loading
    of the page, so that this result is only calculated once
    per page load.
    """
    result = []
    for app_id in get_app_ids_in_domain(domain):
        app = get_latest_released_app(domain, app_id)
        if app and not app.is_deleted() and not app.is_remote_app():
            for module in app.get_modules():
                for form in module.get_forms():
                    if isinstance(form, AdvancedForm) and form.schedule and form.schedule.enabled:
                        result.append({
                            'id': get_combined_id(app_id, form.unique_id),
                            'text': form.full_path_name,
                        })
    return result


class MessagingRecipientHandler(BaseAsyncHandler):
    slug = 'scheduling_select2_helper'

    allowed_actions = [
        'schedule_user_recipients',
        'schedule_user_group_recipients',
        'schedule_user_organization_recipients',
        'schedule_location_types',
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
        return get_groups_by_querystring(domain, query, case_sharing_only)

    @property
    def schedule_user_organization_recipients_response(self):
        return self._get_user_organization_response()

    def _get_user_organization_response(self, case_sharing_only=False):
        from corehq.apps.locations.views import LocationOptionsController
        controller = LocationOptionsController(self.request, self.request.domain,
                                               self.data.get('searchString'),
                                               case_sharing_only=case_sharing_only)
        (count, results) = controller.get_options()
        return results[:10]

    @property
    def schedule_location_types_response(self):
        domain = self.request.domain
        query = self.data.get('searchString')

        qs = LocationType.objects.filter(domain=domain)
        if query:
            qs = qs.filter(name__icontains=query)

        qs = qs.order_by('name').values_list('id', 'name')

        return [
            {'id': row[0], 'text': row[1]}
            for row in qs[:10]
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


class ConditionalAlertAsyncHandler(MessagingRecipientHandler):

    allowed_actions = [
        'schedule_user_recipients',
        'schedule_user_group_recipients',
        'schedule_user_organization_recipients',
        'schedule_location_types',
        'schedule_case_group_recipients',
        'schedule_visit_scheduler_app_and_form_unique_id',
    ]

    @property
    def schedule_visit_scheduler_app_and_form_unique_id_response(self):
        domain = self.request.domain
        timestamp = self.data.get('timestamp')
        if not timestamp:
            raise ValueError("Expected timestamp to be passed")

        query = self.data.get('searchString').lower()
        all_forms = get_visit_scheduler_forms(domain, timestamp)

        filtered_result = [
            entry for entry in all_forms
            if not query or query in entry['text'].lower()
        ]
        return filtered_result[:10]


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
