from datetime import datetime
import logging
from couchdbkit.exceptions import ResourceNotFound
from dateutil.relativedelta import relativedelta
from corehq.apps.hqwebapp.forms import BulkUploadForm
from dimagi.utils.django.email import send_HTML_email
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.views.generic import TemplateView

from corehq.apps.hqwebapp.views import logout
from corehq.apps.registration.forms import NewWebUserRegistrationForm
from corehq.apps.registration.utils import activate_new_user
from corehq.apps.users.models import Invitation, CouchUser, WebUser, DomainInvitation

logger = logging.getLogger(__name__)


def send_confirmation_email(invitation):
    invited_user = invitation.email
    subject = '%s accepted your invitation to CommCare HQ' % invited_user
    recipient = WebUser.get_by_user_id(invitation.invited_by).get_email()
    context = {
        'invited_user': invited_user,
    }
    html_content = render_to_string('domain/email/invite_confirmation.html',
                                    context)
    text_content = render_to_string('domain/email/invite_confirmation.txt',
                                    context)
    send_HTML_email(subject, recipient, html_content,
                    text_content=text_content)


class InvitationView():
    # todo cleanup this view so it properly inherits from BaseSectionPageView
    inv_type = Invitation
    template = ""
    need = [] # a list of strings containing which parameters of the call function should be set as attributes to self

    def added_context(self):
        return {}

    def validate_invitation(self, invitation):
        pass

    def is_invited(self, invitation, couch_user):
        raise NotImplementedError

    @property
    def success_msg(self):
        return _("You have been successfully invited")

    @property
    def redirect_to_on_success(self):
        raise NotImplementedError

    @property
    def inviting_entity(self):
        raise NotImplementedError

    def invite(self, invitation, user):
        raise NotImplementedError

    def _invite(self, invitation, user):
        self.invite(invitation, user)
        invitation.is_accepted = True
        invitation.save()
        messages.success(self.request, self.success_msg)
        send_confirmation_email(invitation)

    def __call__(self, request, invitation_id, **kwargs):
        logging.warning("Don't use this view in more apps until it gets cleaned up.")
        # add the correct parameters to this instance
        self.request = request
        for k, v in kwargs.iteritems():
            if k in self.need:
                setattr(self, k, v)

        if request.GET.get('switch') == 'true':
            logout(request)
            return redirect_to_login(request.path)
        if request.GET.get('create') == 'true':
            logout(request)
            return HttpResponseRedirect(request.path)

        try:
            invitation = self.inv_type.get(invitation_id)
        except ResourceNotFound:
            messages.error(request, _("Sorry, it looks like your invitation has expired. "
                                      "Please check the invitation link you received and try again, or request a "
                                      "project administrator to send you the invitation again."))
            return HttpResponseRedirect(reverse("login"))
        if invitation.is_accepted:
            messages.error(request, _("Sorry, that invitation has already been used up. "
                                      "If you feel this is a mistake please ask the inviter for "
                                      "another invitation."))
            return HttpResponseRedirect(reverse("login"))

        self.validate_invitation(invitation)

        if invitation.invited_on.date() + relativedelta(months=1) < datetime.now().date()  and isinstance(invitation, DomainInvitation):
            return HttpResponseRedirect(reverse("no_permissions"))

        if request.user.is_authenticated():
            is_invited_user = request.couch_user.username.lower() == invitation.email.lower()
            if self.is_invited(invitation, request.couch_user) and not request.couch_user.is_superuser:
                if is_invited_user:
                    # if this invite was actually for this user, just mark it accepted
                    messages.info(request, _("You are already a member of {entity}.").format(
                        entity=self.inviting_entity))
                    invitation.is_accepted = True
                    invitation.save()
                else:
                    messages.error(request, _("It looks like you are trying to accept an invitation for "
                                             "{invited} but you are already a member of {entity} with the "
                                             "account {current}. Please sign out to accept this invitation "
                                             "as another user.").format(
                                                 entity=self.inviting_entity,
                                                 invited=invitation.email,
                                                 current=request.couch_user.username,
                                             ))
                return HttpResponseRedirect(self.redirect_to_on_success)

            if not is_invited_user:
                messages.error(request, _("The invited user {invited} and your user {current} do not match!").format(
                    invited=invitation.email, current=request.couch_user.username))

            if request.method == "POST":
                couch_user = CouchUser.from_django_user(request.user)
                self._invite(invitation, couch_user)
                return HttpResponseRedirect(self.redirect_to_on_success)
            else:
                mobile_user = CouchUser.from_django_user(request.user).is_commcare_user()
                context = self.added_context()
                context.update({
                    'mobile_user': mobile_user,
                    "invited_user": invitation.email if request.couch_user.username != invitation.email else "",
                })
                return render(request, self.template, context)
        else:
            if request.method == "POST":
                form = NewWebUserRegistrationForm(request.POST)
                if form.is_valid():
                    # create the new user
                    user = activate_new_user(form)
                    user.save()
                    messages.success(request, _("User account for %s created! You may now login.")
                                                % form.cleaned_data["email"])
                    self._invite(invitation, user)
                    return HttpResponseRedirect(reverse("login"))
            else:
                form = NewWebUserRegistrationForm(initial={'email': invitation.email})

        return render(request, self.template, {"form": form})


def get_bulk_upload_form(context):
    return BulkUploadForm(
        context['bulk_upload']['plural_noun'],
        context['bulk_upload'].get('action'),
    )
