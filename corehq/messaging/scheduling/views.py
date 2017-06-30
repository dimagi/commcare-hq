from functools import wraps

from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.models import Domain
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.hqwebapp.decorators import use_datatables
from corehq.apps.hqwebapp.views import DataTablesAJAXPaginationMixin
from corehq.messaging.scheduling.models import (
    ImmediateBroadcast,
    ScheduledBroadcast
)
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user

from dimagi.utils.decorators.memoized import memoized


def _requires_new_reminder_framework():
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if not hasattr(request, 'project'):
                request.project = Domain.get_by_name(request.domain)
            if request.project.uses_new_reminders:
                return fn(request, *args, **kwargs)
            raise Http404()
        return wrapped
    return decorate


class BroadcastListView(BaseMessagingSectionView, DataTablesAJAXPaginationMixin):
    template_name = 'scheduling/broadcasts_list.html'
    urlname = 'new_list_broadcasts'
    page_title = ugettext_lazy('Schedule a Message')

    LIST_SCHEDULED = 'list_scheduled'
    LIST_IMMEDIATE = 'list_immediate'

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @use_datatables
    def dispatch(self, *args, **kwargs):
        return super(BroadcastListView, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)

    def _format_time(self, time):
        user_time = ServerTime(time).user_time(self.project_timezone)
        return user_time.ui_string(SERVER_DATETIME_FORMAT)

    def get_scheduled_ajax_response(self):
        query = (
            ScheduledBroadcast.objects
            .filter(domain=self.domain)
            .order_by('-last_sent_timestamp')
        )
        total_records = query.count()
        query = query.select_related('schedule')
        broadcasts = query[self.display_start:self.display_start + self.display_length]

        data = []
        for broadcast in broadcasts:
            data.append([
                broadcast.id,
                broadcast.name,
                self._format_time(broadcast.last_sent_timestamp),
                broadcast.schedule.active,
            ])
        return self.datatables_ajax_response(data, total_records)

    def get_immediate_ajax_response(self):
        query = (
            ImmediateBroadcast.objects
            .filter(domain=self.domain)
            .order_by('-last_sent_timestamp')
        )
        total_records = query.count()
        broadcasts = query[self.display_start:self.display_start + self.display_length]

        data = []
        for broadcast in broadcasts:
            data.append([
                broadcast.name,
                self._format_time(broadcast.last_sent_timestamp),
                broadcast.id,
            ])
        return self.datatables_ajax_response(data, total_records)

    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        if action == self.LIST_SCHEDULED:
            return self.get_scheduled_ajax_response()
        elif action == self.LIST_IMMEDIATE:
            return self.get_immediate_ajax_response()

        return super(BroadcastListView, self).get(*args, **kwargs)


def possible_sms_recipients(request, domain):
    # TODO Add case groups
    # TODO Add locations
    # TODO Add mobile worker groups
    # TODO will need to know doc type as well
    # TODO proper authentication
    query = request.GET.get('name', '').lower()
    users = get_search_users_in_domain_es_query(domain, query, 10, 0)
    users = users.mobile_users().source(('_id', 'base_username')).run().hits
    ret = [
        {'id': user['_id'], 'name': user['base_username']}
        for user in users
    ]
    return JsonResponse(ret, safe=False)
