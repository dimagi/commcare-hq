from datetime import datetime

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.signing import BadSignature, SignatureExpired
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.debug import sensitive_post_parameters

from no_exceptions.exceptions import Http400
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm
from two_factor.views import LoginView

from corehq.apps.domain.decorators import two_factor_exempt
from corehq.apps.users.models import CouchUser
from corehq.util.view_utils import reverse as hq_reverse

from .decorators import consumer_user_login_required
from .forms.change_contact_details_form import ChangeContactDetailsForm
from .forms.consumer_user_authentication_form import (
    ConsumerUserAuthenticationForm,
)
from .forms.consumer_user_signup_form import ConsumerUserSignUpForm
from .models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)


class ConsumerUserLoginView(LoginView):
    form_list = (
        ('auth', ConsumerUserAuthenticationForm),
        ('token', AuthenticationTokenForm),
        ('backup', BackupTokenForm),
    )
    invitation = None
    signed_invitation_id = None
    template_name = 'consumer_user/p_login.html'

    @two_factor_exempt
    @method_decorator(sensitive_post_parameters('password'))
    def dispatch(self, request, *args, **kwargs):
        if 'signed_invitation_id' in kwargs:
            # User is using a link from an invitation
            self.signed_invitation_id = kwargs['signed_invitation_id']
            self.invitation = _get_invitation_or_400(self.signed_invitation_id)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self, step=None):
        """
        Returns the keyword arguments for instantiating the form
        (or formset) on the given step.
        """
        if self.invitation:
            return {'invitation': self.invitation}
        return {}

    def get_success_url(self):
        return self.get_redirect_url() or reverse('consumer_user:homepage')

    def get_context_data(self, **kwargs):
        context = super(ConsumerUserLoginView, self).get_context_data(**kwargs)
        if self.signed_invitation_id:
            context['go_to_signup'] = hq_reverse(
                'consumer_user:register',
                kwargs={'signed_invitation_id': self.signed_invitation_id},
                params={'create_user': '1'},
            )
        context['hide_menu'] = True
        return context


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
        }
    )


@consumer_user_login_required
def homepage_view(request):
    return render(request, 'consumer_user/homepage.html')


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
        return render(request, 'consumer_user/change_password.html', {'form': form})
    else:
        form = PasswordChangeForm(user=request.user)
        return render(request, 'consumer_user/change_password.html', {'form': form})


@consumer_user_login_required
def domains_and_cases_list_view(request):
    consumer_user = get_object_or_404(ConsumerUser, user=request.user)
    domains_and_cases = list(
        ConsumerUserCaseRelationship.objects
        .filter(consumer_user=consumer_user)
        .values('domain', 'case_id')
    )

    return render(request, 'consumer_user/domains_and_cases.html', {'domains_and_cases': domains_and_cases})


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
    return render(request, 'consumer_user/change_contact_details.html', {'form': form})


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
