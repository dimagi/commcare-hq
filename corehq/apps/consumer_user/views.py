from datetime import datetime

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.views.decorators.debug import sensitive_post_parameters

from two_factor.forms import AuthenticationTokenForm, BackupTokenForm
from two_factor.views import LoginView

from corehq.apps.consumer_user.models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
)
from corehq.apps.consumer_user.util import InvitationError, get_invitation_obj
from corehq.apps.domain.decorators import two_factor_exempt

from ..users.models import CouchUser
from .decorators import consumer_user_login_required
from .forms.change_contact_details_form import ChangeContactDetailsForm
from .forms.consumer_user_authentication_form import (
    ConsumerUserAuthenticationForm,
)
from .forms.consumer_user_signup_form import ConsumerUserSignUpForm


class ConsumerUserLoginView(LoginView):
    form_list = (
        ('auth', ConsumerUserAuthenticationForm),
        ('token', AuthenticationTokenForm),
        ('backup', BackupTokenForm),
    )
    invitation = None
    hashed_invitation = None
    template_name = 'consumer_user/p_login.html'

    def get_form_kwargs(self, step=None):
        """
        Returns the keyword arguments for instantiating the form
        (or formset) on the given step.
        """
        if self.invitation:
            return {'invitation': self.invitation}
        return {}

    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        url = reverse('consumer_user:consumer_user_homepage')
        return url

    def get_context_data(self, **kwargs):
        context = super(ConsumerUserLoginView, self).get_context_data(**kwargs)
        if self.hashed_invitation:
            extra_context = {}
            go_to_signup = reverse('consumer_user:consumer_user_register',
                                   kwargs={
                                       'invitation': self.hashed_invitation
                                   })
            extra_context['go_to_signup'] = '%s%s' % (go_to_signup, '?create_user=1')
            context.update(extra_context)
        context.update({'hide_menu': True})
        return context


@two_factor_exempt
def register_view(request, invitation):
    try:
        invitation_obj = get_invitation_obj(invitation)
    except InvitationError as err:
        return HttpResponse(err.msg, status=err.status)
    if isinstance(invitation_obj, HttpResponse):
        return invitation_obj
    email = invitation_obj.email
    create_user = request.GET.get('create_user', False)
    if create_user != '1' and User.objects.filter(username=email).exists():
        url = reverse('consumer_user:consumer_user_login_with_invitation',
                      kwargs={
                          'invitation': invitation
                      })
        return HttpResponseRedirect(url)
    if request.method == "POST":
        form = ConsumerUserSignUpForm(request.POST, invitation=invitation_obj)
        if form.is_valid():
            form.save()
            url = reverse('consumer_user:consumer_user_login')
            return HttpResponseRedirect(url)
    else:
        form = ConsumerUserSignUpForm()
    return render(request, 'consumer_user/signup.html', {'form': form,
                                                         'hide_menu': True})


@two_factor_exempt
@sensitive_post_parameters('auth-password')
def login_view(request, invitation=None):
    if invitation:
        return login_accept_view(request, invitation)
    if request.user and request.user.is_authenticated:
        consumer_user = ConsumerUser.objects.get_or_none(user=request.user)
        if consumer_user:
            url = reverse('consumer_user:consumer_user_homepage')
            return HttpResponseRedirect(url)
    return ConsumerUserLoginView.as_view()(request)


def login_accept_view(request, invitation):
    try:
        invitation_obj = get_invitation_obj(invitation)
    except InvitationError as err:
        return HttpResponse(err.msg, status=err.status)
    if isinstance(invitation_obj, HttpResponse):
        return invitation_obj
    return ConsumerUserLoginView.as_view(invitation=invitation_obj, hashed_invitation=invitation)(request)


@consumer_user_login_required
def success_view(request):
    return render(request, 'consumer_user/homepage.html')


@consumer_user_login_required
def logout_view(request):
    logout(request)
    url = reverse('consumer_user:consumer_user_login')
    return HttpResponseRedirect(url)


@consumer_user_login_required
def change_password_view(request):
    consumer_user = ConsumerUser.objects.get_or_none(user=request.user)
    if consumer_user:
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
    else:
        return HttpResponse(status=404)


@consumer_user_login_required
def domains_and_cases_list_view(request):
    consumer_user = ConsumerUser.objects.get_or_none(user=request.user)
    if consumer_user:
        qs = ConsumerUserCaseRelationship.objects.filter(consumer_user=consumer_user)
        domains_and_cases = [val for val in qs.values('domain', 'case_id')]
        return render(request, 'consumer_user/domains_and_cases.html', {'domains_and_cases': domains_and_cases})
    else:
        return HttpResponse(status=404)


@consumer_user_login_required
def change_contact_details_view(request):
    consumer_user = ConsumerUser.objects.get_or_none(user=request.user)
    if consumer_user:
        if request.method == 'POST':
            form = ChangeContactDetailsForm(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, _('Updated Successfully'))
        else:
            form = ChangeContactDetailsForm(instance=request.user)
        return render(request, 'consumer_user/change_contact_details.html', {'form': form})
    else:
        return HttpResponse(status=404)
