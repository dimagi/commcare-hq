from functools import wraps

from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.models import Domain
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.style.decorators import use_datatables
from corehq.apps.hqwebapp.views import DataTablesAJAXPaginationMixin
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
    # TODO: should use template in its own folder
    template_name = 'reminders/broadcasts_list.html'
    urlname = 'new_list_broadcasts'
    page_title = ugettext_lazy('Schedule a Message')

    @method_decorator(_requires_new_reminder_framework())
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @use_datatables
    def dispatch(self, *args, **kwargs):
        return super(BroadcastListView, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)
