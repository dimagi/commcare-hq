from memoized import memoized

from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404
from django.utils.translation import gettext_lazy, gettext as _

from corehq.apps.data_cleaning.exceptions import SessionAccessClosedException
from corehq.apps.data_cleaning.models import BulkEditSession


class BulkEditSessionViewMixin:
    session_not_found_message = gettext_lazy("That session does not exist. Please start a new session.")
    redirect_on_session_exceptions = False

    @property
    def session_id(self):
        return self.kwargs['session_id']

    def get_redirect_url(self):
        raise NotImplementedError(
            "get_redirect_url must be implemented in the subclass of BulkEditSessionViewMixin "
            "in order to use redirect_on_session_exceptions"
        )

    @property
    @memoized
    def session(self):
        session = BulkEditSession.objects.get(
            user=self.request.user,
            domain=self.domain,
            session_id=self.session_id,
        )
        if session.completed_on:
            raise SessionAccessClosedException(_(
                "You tried to access a session for \"{}\" that was already completed. "
                "Please start a new session."
            ).format(session.identifier))
        elif session.committed_on:
            raise SessionAccessClosedException(_(
                "You tried to access a session for \"{}\" that is currently applying changes. "
                "Please wait for that task to complete, then start a new session."
            ).format(session.identifier))
        return session

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'session': self.session,
            'session_id': self.session_id,
        })
        return context

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)

        except BulkEditSession.DoesNotExist:

            if self.redirect_on_session_exceptions:
                messages.error(request, self.session_not_found_message)
                return redirect(self.get_redirect_url())

            raise Http404(self.session_not_found_message)

        except SessionAccessClosedException as error:

            if self.redirect_on_session_exceptions:
                messages.warning(request, str(error))
                return redirect(self.get_redirect_url())

            return Http404(error.msg)
