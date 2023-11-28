from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.html import format_html
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.registration.models import AsyncSignupRequest
from corehq.apps.sso.models import IdentityProvider
from dimagi.utils.couch import CriticalSection

from corehq.apps.accounting.decorators import always_allow_project_access
from corehq.apps.analytics.tasks import (
    HUBSPOT_EXISTING_USER_INVITE_FORM,
    HUBSPOT_NEW_USER_INVITE_FORM,
    send_hubspot_form,
    track_workflow,
)
from corehq.apps.domain.extension_points import has_custom_clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.views import BasePageView, logout
from corehq.apps.locations.permissions import location_safe
from corehq.apps.registration.forms import WebUserInvitationForm
from corehq.apps.registration.utils import activate_new_user_via_reg_form
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.decorators import require_can_edit_web_users
from corehq.apps.users.forms import DomainRequestForm
from corehq.apps.users.models import CouchUser, DomainRequest, Invitation
from corehq.apps.users.util import log_user_change
from corehq.const import USER_CHANGE_VIA_INVITATION


class UserInvitationView(object):
    # todo cleanup this view so it properly inherits from BaseSectionPageView
    template = "users/accept_invite.html"

    def __call__(self, request, uuid, **kwargs):
        # add the correct parameters to this instance
        self.request = request
        if 'domain' in kwargs:
            self.domain = kwargs['domain']

        if request.GET.get('switch') == 'true':
            logout(request)
            return redirect_to_login(request.path)
        if request.GET.get('create') == 'true':
            logout(request)
            return HttpResponseRedirect(request.path)
        try:
            invitation = Invitation.objects.get(uuid=uuid)
        except (Invitation.DoesNotExist, ValidationError):
            messages.error(request, _("Sorry, it looks like your invitation has expired. "
                                      "Please check the invitation link you received and try again, or "
                                      "request a project administrator to send you the invitation again."))
            return HttpResponseRedirect(reverse("login"))

        is_invited_user = (request.user.is_authenticated
            and request.couch_user.username.lower() == invitation.email.lower())

        if invitation.is_accepted:
            if request.user.is_authenticated and not is_invited_user:
                messages.error(request, _("Sorry, that invitation has already been used up. "
                                          "If you feel this is a mistake, please ask the inviter for "
                                          "another invitation."))
            return HttpResponseRedirect(reverse("login"))

        self.validate_invitation(invitation)

        if invitation.is_expired:
            return HttpResponseRedirect(reverse("no_permissions"))

        username = self.request.user.username
        if username:
            userhalf, domainhalf = username.split('@')
            # Add zero-width space to username for better line breaking
            formatted_username = format_html('{}&#x200b;@{}', userhalf, domainhalf)
        else:
            formatted_username = username

        context = {
            'formatted_username': formatted_username,
            'domain': self.domain,
            'invite_to': self.domain,
            'invite_type': _('Project'),
            'hide_password_feedback': has_custom_clean_password(),
            'button_label': _('Create Account')
        }
        if request.user.is_authenticated:
            context['current_page'] = {'page_name': _('Project Invitation')}
        else:
            context['current_page'] = {'page_name': _('Project Invitation, Account Required')}
        if request.user.is_authenticated:
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
                                                 current=request.couch_user.username))
                return HttpResponseRedirect(self.redirect_to_on_success(invitation.email, self.domain))

            if not is_invited_user:
                messages.error(request, _("The invited user {invited} and your user {current} "
                    "do not match!").format(invited=invitation.email, current=request.couch_user.username))

            if request.method == "POST":
                couch_user = CouchUser.from_django_user(request.user, strict=True)
                invitation.accept_invitation_and_join_domain(couch_user)
                log_user_change(
                    by_domain=invitation.domain,
                    for_domain=invitation.domain,
                    couch_user=couch_user,
                    changed_by_user=CouchUser.get_by_user_id(invitation.invited_by),
                    changed_via=USER_CHANGE_VIA_INVITATION,
                    change_messages=UserChangeMessage.domain_addition(invitation.domain)
                )
                track_workflow(request.couch_user.get_email(),
                               "Current user accepted a project invitation",
                               {"Current user accepted a project invitation": "yes"})
                send_hubspot_form(HUBSPOT_EXISTING_USER_INVITE_FORM, request)
                return HttpResponseRedirect(self.redirect_to_on_success(invitation.email, self.domain))
            else:
                mobile_user = CouchUser.from_django_user(request.user).is_commcare_user()
                context.update({
                    'mobile_user': mobile_user,
                    "invited_user": invitation.email if request.couch_user.username != invitation.email else "",
                })
                return render(request, self.template, context)
        else:
            domain_obj = Domain.get_by_name(invitation.domain)
            allow_invite_email_only = domain_obj and domain_obj.allow_invite_email_only

            idp = None
            if settings.ENFORCE_SSO_LOGIN:
                idp = IdentityProvider.get_required_identity_provider(invitation.email)

            if request.method == "POST":
                form = WebUserInvitationForm(
                    request.POST,
                    is_sso=idp is not None,
                    allow_invite_email_only=allow_invite_email_only,
                    invite_email=invitation.email)
                if form.is_valid():
                    # create the new user
                    invited_by_user = CouchUser.get_by_user_id(invitation.invited_by)

                    if idp:
                        signup_request = AsyncSignupRequest.create_from_invitation(invitation)
                        return HttpResponseRedirect(idp.get_login_url(signup_request.username))

                    if allow_invite_email_only and \
                            request.POST.get("email").lower() != invitation.email.lower():
                        messages.error(request, _("You can only sign up with the email "
                                                  "address your invitation was sent to."))
                        return HttpResponseRedirect(reverse("login"))

                    user = activate_new_user_via_reg_form(
                        form,
                        created_by=invited_by_user,
                        created_via=USER_CHANGE_VIA_INVITATION,
                        domain=invitation.domain,
                        is_domain_admin=False,
                    )
                    user.save()
                    messages.success(request, _("User account for %s created!") % form.cleaned_data["email"])
                    invitation.accept_invitation_and_join_domain(user)
                    messages.success(
                        self.request,
                        _('You have been added to the "{}" project space.').format(self.domain)
                    )
                    authenticated = authenticate(username=form.cleaned_data["email"],
                                                 password=form.cleaned_data["password"], request=request)
                    if authenticated is not None and authenticated.is_active:
                        login(request, authenticated)
                    track_workflow(request.POST['email'],
                                   "New User Accepted a project invitation",
                                   {"New User Accepted a project invitation": "yes"})
                    send_hubspot_form(HUBSPOT_NEW_USER_INVITE_FORM, request, user)
                    return HttpResponseRedirect(self.redirect_to_on_success(invitation.email, invitation.domain))
            else:
                if (CouchUser.get_by_username(invitation.email)
                        or User.objects.filter(username__iexact=invitation.email).count() > 0):
                    login_url = reverse("login")
                    accept_invitation_url = reverse(
                        'domain_accept_invitation',
                        args=[invitation.domain, invitation.uuid]
                    )
                    return HttpResponseRedirect(
                        f"{login_url}"
                        f"?next={accept_invitation_url}"
                        f"&username={invitation.email}"
                    )
                form = WebUserInvitationForm(
                    initial={
                        'email': invitation.email,
                    },
                    is_sso=idp is not None,
                    allow_invite_email_only=allow_invite_email_only
                )

            context.update({
                'is_sso': idp is not None,
                'idp_name': idp.name if idp else None,
                'invited_user': invitation.email,
            })

        context.update({"form": form})
        return render(request, self.template, context)

    def validate_invitation(self, invitation):
        assert invitation.domain == self.domain

    def is_invited(self, invitation, couch_user):
        return couch_user.is_member_of(invitation.domain)

    @property
    def inviting_entity(self):
        return self.domain

    def redirect_to_on_success(self, email, domain):
        if Invitation.by_email(email).count() > 0 and not self.request.GET.get('no_redirect'):
            return reverse("domain_select_redirect")
        else:
            return reverse("domain_homepage", args=[domain])


@waf_allow('XSS_BODY')
@always_allow_project_access
@location_safe
@sensitive_post_parameters('password')
def accept_invitation(request, domain, uuid):
    from corehq.apps.users.views.web import UserInvitationView
    return UserInvitationView()(request, uuid, domain=domain)


@always_allow_project_access
@require_POST
@require_can_edit_web_users
def reinvite_web_user(request, domain):
    uuid = request.POST['uuid']
    try:
        invitation = Invitation.objects.get(uuid=uuid)
    except Invitation.DoesNotExist:
        return JsonResponse({'response': _("Error while attempting resend"), 'status': 'error'})

    invitation.invited_on = datetime.utcnow()
    invitation.save()
    invitation.send_activation_email()
    return JsonResponse({'response': _("Invitation resent"), 'status': 'ok'})


@always_allow_project_access
@require_POST
@require_can_edit_web_users
def delete_invitation(request, domain):
    uuid = request.POST['uuid']
    invitation = Invitation.objects.get(uuid=uuid)
    invitation.delete()
    return JsonResponse({'status': 'ok'})


@method_decorator(always_allow_project_access, name='dispatch')
class DomainRequestView(BasePageView):
    urlname = "domain_request"
    page_title = gettext_lazy("Request Access")
    template_name = "users/domain_request.html"
    request_form = None

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.request.domain])

    @property
    def page_context(self):
        domain_obj = Domain.get_by_name(self.request.domain)
        if self.request_form is None:
            initial = {'domain': domain_obj.name}
            if self.request.user.is_authenticated:
                initial.update({
                    'email': self.request.user.get_username(),
                    'full_name': self.request.user.get_full_name(),
                })
            self.request_form = DomainRequestForm(initial=initial)
        return {
            'domain': domain_obj.name,
            'hr_name': domain_obj.display_name(),
            'request_form': self.request_form,
        }

    def post(self, request, *args, **kwargs):
        self.request_form = DomainRequestForm(request.POST)
        if self.request_form.is_valid():
            data = self.request_form.cleaned_data
            with CriticalSection(["domain_request_%s" % data['domain']]):
                if DomainRequest.by_email(data['domain'], data['email']) is not None:
                    messages.error(request, _("A request is pending for this email. "
                        "You will receive an email when the request is approved."))
                else:
                    domain_request = DomainRequest(**data)
                    domain_request.send_request_email()
                    domain_request.save()
                    domain_obj = Domain.get_by_name(domain_request.domain)
                    return render(request, "users/confirmation_sent.html", {
                        'hr_name': domain_obj.display_name() if domain_obj else domain_request.domain,
                    })
        return self.get(request, *args, **kwargs)
