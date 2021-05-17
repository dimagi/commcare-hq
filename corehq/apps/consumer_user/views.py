from datetime import datetime

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.signing import BadSignature, SignatureExpired
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.debug import sensitive_post_parameters

from no_exceptions.exceptions import Http400
from two_factor.views import LoginView

from corehq.apps.domain.decorators import two_factor_exempt
from corehq.apps.users.models import CouchUser
from corehq.util.view_utils import reverse as hq_reverse

from .decorators import consumer_user_login_required
from .forms import (
    ChangeContactDetailsForm,
    ConsumerUserSignUpForm,
)
from .models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)


class ConsumerUserLoginView(LoginView):
    invitation = None
    signed_invitation_id = None
    template_name = 'consumer_user/login.html'

    @two_factor_exempt
    @method_decorator(sensitive_post_parameters('password'))
    def dispatch(self, request, *args, **kwargs):
        if 'signed_invitation_id' in kwargs:
            # User is using a link from an invitation
            self.signed_invitation_id = kwargs['signed_invitation_id']
            self.invitation = _get_invitation_or_400(self.signed_invitation_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.get_redirect_url() or reverse('consumer_user:homepage')

    def get_context_data(self, **kwargs):
        context = super(ConsumerUserLoginView, self).get_context_data(**kwargs)
        if self.signed_invitation_id:
            context['invitation_email'] = self.invitation.email
            context['register_url'] = hq_reverse(
                'consumer_user:register',
                kwargs={'signed_invitation_id': self.signed_invitation_id},
                params={'create_user': '1'},
            )
        context['hide_menu'] = True
        context['restrict_domain_creation'] = True
        return context

    def done(self, *args, **kwargs):
        if self.invitation and not self.invitation.accepted:
            # If a WebUser was signed in and clicked an invitation link, we
            # create a ConsumerUser here
            consumer_user, created = ConsumerUser.objects.get_or_create(user=self.get_user())
            self.invitation.accept_for_consumer_user(consumer_user)
        return super().done(*args, **kwargs)


@two_factor_exempt
@sensitive_post_parameters('password')
def register_view(request, signed_invitation_id):

    invitation = _get_invitation_or_400(signed_invitation_id)

    if invitation.accepted:
        return HttpResponseRedirect(reverse('consumer_user:login'))

    email = invitation.email
    create_user = request.GET.get('create_user', False)
    if create_user != '1' and User.objects.filter(username=email).exists():
        url = reverse(
            'consumer_user:login_with_invitation',
            kwargs={'signed_invitation_id': signed_invitation_id}
        )
        return HttpResponseRedirect(url)
    if request.method == "POST":
        form = ConsumerUserSignUpForm(request.POST, invitation=invitation)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('consumer_user:login'))
    else:
        form = ConsumerUserSignUpForm(initial={'email': email})
    return render(
        request,
        'consumer_user/signup.html',
        {
            'form': form,
            'hide_menu': True,
            'domain': invitation.domain,
            'invitation_email': invitation.email,
            'login_url': reverse(
                'consumer_user:login_with_invitation',
                kwargs={'signed_invitation_id': signed_invitation_id}
            )
        }
    )


@consumer_user_login_required
def homepage_view(request):
    consumer_user = get_object_or_404(ConsumerUser, user=request.user)
    cases = list(
        ConsumerUserCaseRelationship.objects
        .filter(consumer_user=consumer_user)
        .values('domain', 'case_id')
    )

    return render(request, 'consumer_user/homepage.html', {'cases': cases})


@consumer_user_login_required
def logout_view(request):
    logout(request)
    url = reverse('consumer_user:login')
    return HttpResponseRedirect(url)


@consumer_user_login_required
def change_password_view(request):
    # Check this is actually a ConsumerUser
    get_object_or_404(ConsumerUser, user=request.user)

    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            couch_user = CouchUser.from_django_user(request.user)
            if couch_user:
                couch_user.last_password_set = datetime.utcnow()
                couch_user.save()
            messages.success(request, _('Updated Successfully'))
    else:
        form = PasswordChangeForm(user=request.user)

    return render(
        request,
        'consumer_user/consumer_user_form.html',
        {'form': form, 'page_title': _("Change Password")},
    )


@consumer_user_login_required
def change_contact_details_view(request):
    get_object_or_404(ConsumerUser, user=request.user)
    if request.method == 'POST':
        form = ChangeContactDetailsForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Updated Successfully'))
    else:
        form = ChangeContactDetailsForm(instance=request.user)
    return render(
        request,
        'consumer_user/consumer_user_form.html',
        {'form': form, 'page_title': _('Change Contact Details')},
    )


def _get_invitation_or_400(signed_invitation_id):
    try:
        invitation = ConsumerUserInvitation.from_signed_id(signed_invitation_id)
    except (BadSignature, ConsumerUserInvitation.DoesNotExist):
        raise Http400(_("Invitation Not Found"))
    except SignatureExpired:
        raise Http400(_("Invitation expired"))

    if not invitation.active:
        raise Http400(_("Invitation expired"))

    return invitation
