from memoized import memoized

from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404
from django.utils.translation import gettext_lazy
from corehq.apps.data_cleaning.models import BulkEditSession


class BulkEditSessionViewMixin:
    session_not_found_message = gettext_lazy("That session does not exist. Please start a new session.")
    redirect_on_session_exceptions = False

    @property
    def session_id(self):
        return self.kwargs['session_id']

    def get_redirect_url(self):
        """
        Return the URL to redirect to if the session is missing.
        Only used when `redirect_on_missing_session` is True.
        """
        raise NotImplementedError(
            "get_redirect_url must be implemented in the subclass of BulkEditSessionViewMixin "
            "in order to use redirect_on_session_exceptions"
        )

    @property
    @memoized
    def session(self):
        return BulkEditSession.objects.get(
            user=self.request.user,
            domain=self.domain,
            session_id=self.session_id,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'session': self.session,
            'session_id': self.session_id,
        })
        return context

    def dispatch(self, request, *args, **kwargs):
        try:
            # force evaluation of self.session
            _ = self.session
        except BulkEditSession.DoesNotExist:
            if self.redirect_on_missing_session:
                messages.error(request, self.session_not_found_message)
                return redirect(self.get_redirect_url())
            raise Http404(self.session_not_found_message)
        return super().dispatch(request, *args, **kwargs)
