from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render

from corehq.apps.hqwebapp.views import logout
from corehq.apps.registration.forms import NewWebUserRegistrationForm
from corehq.apps.registration.utils import activate_new_user
from corehq.apps.users.models import Invitation, CouchUser


class InvitationView():
    inv_type = Invitation
    template = ""
    need = [] # a list of strings containing which parameters of the call function should be set as attributes to self

    def added_context(self):
        return {}

    def validate_invitation(self, invitation):
        pass

    @property
    def success_msg(self):
        return "You have been successfully invited"

    @property
    def redirect_to_on_success(self):
        raise NotImplementedError

    def invite(self, invitation, user):
        raise NotImplementedError

    def _invite(self, invitation, user):
        self.invite(invitation, user)
        invitation.is_accepted = True
        invitation.save()
        messages.success(self.request, self.success_msg)

    def __call__(self, request, invitation_id, **kwargs):
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

        invitation = self.inv_type.get(invitation_id)

        if invitation.is_accepted:
            messages.error(request, "Sorry, that invitation has already been used up. "
                                    "If you feel this is a mistake please ask the inviter for "
                                    "another invitation.")
            return HttpResponseRedirect(reverse("login"))

        self.validate_invitation(invitation)

        if request.user.is_authenticated():
            if request.couch_user.username != invitation.email:
                messages.error(request, "The invited user %s and your user %s do not match!" % (invitation.email, request.couch_user.username))

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
                    messages.success(request, "User account for %s created! You may now login." % form.cleaned_data["email"])
                    self._invite(invitation, user)
                    return HttpResponseRedirect(reverse("login"))
            else:
                form = NewWebUserRegistrationForm(initial={'email': invitation.email})

        return render(request, self.template, {"form": form})

