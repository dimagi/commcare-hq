import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.signing import TimestampSigner
from django.core.signing import Signer
from django.core.signing import BadSignature
from django.core.signing import SignatureExpired
from datetime import timedelta
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.forms.models import model_to_dict

from .forms.change_contact_details_form import ChangeContactDetailsForm
from .forms.patient_signup_form import PatientSignUpForm
from .forms.patient_authentication_form import PatientAuthenticationForm
from django.views.decorators.debug import sensitive_post_parameters
from two_factor.views import LoginView

from corehq.apps.consumer_user.models import ConsumerUser
from corehq.apps.consumer_user.models import ConsumerUserCaseRelationship
from corehq.apps.consumer_user.models import ConsumerUserInvitation
from corehq.apps.domain.decorators import two_factor_exempt
from .decorators import login_required
from django.utils.http import urlsafe_base64_decode
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm
from django.utils.translation import ugettext as _
from ..domain.extension_points import has_custom_clean_password


class PatientLoginView(LoginView):
    form_list = (
        ('auth', PatientAuthenticationForm),
        ('token', AuthenticationTokenForm),
        ('backup', BackupTokenForm),
    )
    invitation = None
    hashed_invitation = None
    template_name = 'two_factor/core/p_login.html'

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
        url = reverse('consumer_user:patient_homepage')
        return url

    def get_context_data(self, **kwargs):
        context = super(PatientLoginView, self).get_context_data(**kwargs)
        extra_context = {}
        if self.hashed_invitation:
            this_is_not_me = reverse('consumer_user:patient_register',
                                     kwargs={
                                         'invitation': self.hashed_invitation
                                     })
            extra_context['this_is_not_me'] = '%s%s' % (this_is_not_me,
                                                        '?create_user=1')
        url = reverse('consumer_user:password_reset_email')
        extra_context['password_reset_url'] = url
        context.update(extra_context)
        return context


def list_view(request):
    pass


@two_factor_exempt
def register_view(request, invitation):
    try:
        decoded_invitation = urlsafe_base64_decode(TimestampSigner().unsign(invitation,
                                                                    max_age=timedelta(days=30)))
        invitation_obj = ConsumerUserInvitation.objects.get(id=decoded_invitation)
        if invitation_obj.accepted:
            url = reverse('consumer_user:patient_login')
            return HttpResponseRedirect(url)
    except (BadSignature, ConsumerUserInvitation.DoesNotExist):
        return JsonResponse({'message': "Invalid invitation"}, status=400)
    except SignatureExpired:
        return JsonResponse({'message': "Invitation is expired"}, status=400)
    email = invitation_obj.email
    hashed_email = Signer().sign(email)
    try:
        create_user = request.GET.get('create_user', False)
        if create_user != '1':
            _ = User.objects.get(username=hashed_email)
            url = reverse('consumer_user:patient_login_with_invitation',
                          kwargs={
                              'invitation': invitation
                          })
            return HttpResponseRedirect(url)
        else:
            pass
    except User.DoesNotExist:
        pass
    if request.method == "POST":
        body = request.POST
        entered_email = request.POST.get('email')
        hashed_username = Signer().sign(entered_email)
        form = PatientSignUpForm(body, invitation=invitation_obj)
        try:
            _ = User.objects.get(username=hashed_username)
            return render(request, 'signup.html', {'form': form,
                                                   'has_errors': True,
                                                   'errors': 'User with email already exists'})
        except User.DoesNotExist:
            pass
        form = PatientSignUpForm(body, invitation=invitation_obj)
        if form.is_valid():
            try:
                _ = form.save()
            except Exception as e:
                return HttpResponse(e)
        url = reverse('consumer_user:patient_login')
        return HttpResponseRedirect(url)
    else:
        form = PatientSignUpForm()
        return render(request, 'signup.html', {'form': form})


@two_factor_exempt
@sensitive_post_parameters('auth-password')
def login_view(request, invitation=None):
    try:
        if invitation:
            return login_accept_view(request, invitation)
        if request.user and request.user.is_authenticated:
            try:
                _ = ConsumerUser.objects.get(user=request.user)
                url = reverse('consumer_user:patient_homepage')
                return HttpResponseRedirect(url)
            except ConsumerUser.DoesNotExist:
                pass
        return PatientLoginView.as_view()(request)
    except (User.DoesNotExist, ConsumerUser.DoesNotExist):
        return JsonResponse({'message': "Patient User does not exist with your email"}, status=400)


def login_accept_view(request, invitation):
    try:
        decoded_invitation = urlsafe_base64_decode(TimestampSigner().unsign(invitation,
                                                                            max_age=timedelta(days=30)))
        invitation_obj = ConsumerUserInvitation.objects.get(id=decoded_invitation)
        if invitation_obj.accepted:
            url = reverse('consumer_user:patient_login')
            return HttpResponseRedirect(url)
    except (BadSignature, ConsumerUserInvitation.DoesNotExist):
        return JsonResponse({'message': "Invalid invitation"}, status=400)
    except SignatureExpired:
        return JsonResponse({'message': "Invitation is expired"}, status=400)
    if request.method == "POST":
        body = request.POST
        username = body.get('auth-username')
        if invitation_obj.email != username:
            return JsonResponse({'message': "Email is not same as the one that the invitation has been sent"},
                                status=400)
    return PatientLoginView.as_view(invitation=invitation_obj,
                                    hashed_invitation=invitation)(request)


@login_required
def success_view(request):
    try:
        username = Signer().unsign(request.user.username)
    except BadSignature:
        username = request.user.email
    return render(request, 'homepage.html', {'username': username})


@login_required
def logout_view(request):
    logout(request)
    url = reverse('consumer_user:patient_login')
    return HttpResponseRedirect(url)


def detail_view(request):
    pass


def delete_view(request):
    pass


class CustomPasswordResetView(PasswordResetConfirmView):
    urlname = 'consumer_user_password_reset_confirm'

    def get_success_url(self):
        if self.user:
            consumer_user = ConsumerUser.objects.get(user=self.user)
            messages.success(
                self.request,
                _('Password for {} has successfully been reset. You can now login.').format(
                    Signer().unsign(consumer_user.user.username)
                )
            )
        return super().get_success_url()

    def get(self, request, *args, **kwargs):
        self.extra_context['hide_password_feedback'] = has_custom_clean_password()
        return super().get(request)

    def post(self, request, *args, **kwargs):
        self.extra_context['hide_password_feedback'] = has_custom_clean_password()
        response = super().post(request)
        return response


def change_password_view(request):
    try:
        if request.user and request.user.is_authenticated:
            _ = ConsumerUser.objects.get(user=request.user)
            msg = None
            if request.method == 'POST':
                form = PasswordChangeForm(user=request.user, data=request.POST)
                if form.is_valid():
                    form.save()
                    msg = 'Updated successfully'
                return render(request, 'change_password.html', {'form': form,
                                                                'msg': msg})
            else:
                form = PasswordChangeForm(user=request.user)
                return render(request, 'change_password.html', {'form': form})
        else:
            url = reverse('consumer_user:patient_login')
            return HttpResponseRedirect(url)
    except (User.DoesNotExist, ConsumerUser.DoesNotExist):
        return JsonResponse({'message': "User does not exist"}, status=400)


def domains_and_cases_list_view(request):
    try:
        if request.user and request.user.is_authenticated:
            consumer_user = ConsumerUser.objects.get(user=request.user)
            qs = ConsumerUserCaseRelationship.objects.filter(case_user=consumer_user)
            domains_and_cases = [val for val in qs.values('domain', 'case_id')]
            return render(request, 'domains_and_cases.html', {'domains_and_cases': domains_and_cases})
        else:
            return JsonResponse({'message': 'Unauthorized access'}, status=401)
    except (User.DoesNotExist, ConsumerUser.DoesNotExist):
        return JsonResponse({'message': "User does not exist"}, status=400)


def change_contact_details_view(request):
    try:
        if request.user and request.user.is_authenticated:
            _ = ConsumerUser.objects.get(user=request.user)
            msg = None
            if request.method == 'POST':
                form = ChangeContactDetailsForm(request.POST, instance=request.user)
                if form.is_valid():
                    form.save()
                    msg = 'Updated successfully'
            else:
                form = ChangeContactDetailsForm(instance=request.user)
            return render(request, 'change_contact_details.html', {'form': form,
                                                                   'msg': msg})
        else:
            return JsonResponse({'message': 'Unauthorized access'}, status=401)
    except (User.DoesNotExist, ConsumerUser.DoesNotExist):
        return JsonResponse({'message': "User does not exist"}, status=400)
