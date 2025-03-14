from django.http import Http404
from django.utils.translation import gettext_lazy
from memoized import memoized

from corehq.apps.data_cleaning.models import BulkEditSession


class BulkEditSessionViewMixin:
    session_not_found_message = gettext_lazy("Data cleaning session was not found.")

    @property
    def session_id(self):
        return self.kwargs['session_id']

    @property
    @memoized
    def session(self):
        try:
            return BulkEditSession.objects.get(session_id=self.session_id)
        except BulkEditSession.DoesNotExist:
            raise Http404(self.session_not_found_message)
