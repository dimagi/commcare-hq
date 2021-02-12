import json

from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.urls import reverse
from django.forms.models import model_to_dict
from .forms.patient_signup_form import PatientSignUpForm
from django.views.decorators.debug import sensitive_post_parameters
from two_factor.views import LoginView
from django.shortcuts import render
from corehq.apps.consumer_user.models import ConsumerUser
from corehq.apps.consumer_user.models import ConsumerUserInvitation
from corehq.apps.consumer_user.models import ConsumerUserCaseRelationship
from corehq.apps.domain.decorators import two_factor_exempt
from .decorators import login_required
from django.utils.http import urlsafe_base64_decode


class PatientLoginView(LoginView):

    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        url = reverse('consumer_user:patient_homepage')
        return url


def list_view(request):
    pass


@two_factor_exempt
def register_view(request, invitation):
    invitation = urlsafe_base64_decode(invitation)
    try:
        invitation_obj = ConsumerUserInvitation.objects.get(id=invitation)
        if invitation_obj.accepted:
            url = reverse('consumer_user:patient_login')
            return HttpResponseRedirect(url)
    except ConsumerUserInvitation.DoesNotExist:
        return JsonResponse({'message': "Invalid invitation"}, status=400)
    email = invitation_obj.email
    if request.method == "POST":
        body = request.POST
        entered_email = body.get('email')
        password = body.get('password')
        consumer_user = None
        try:
            if email != entered_email:
                return JsonResponse({'message': "Email is not same as the one that the invitation has been sent"},
                                    status=400)
            user = User.objects.get(username=email, email=email)
            if not user.check_password(password):
                return JsonResponse({'message': "Existing user but password is different"}, status=400)
            consumer_user = ConsumerUser.objects.get(user=user)
        except User.DoesNotExist:
            form = PatientSignUpForm(body)
            if form.is_valid():
                user = form.save()
        except ConsumerUser.DoesNotExist:
            pass
        if not consumer_user:
            consumer_user = ConsumerUser.objects.create(user=user)
        if invitation_obj:
            invitation_obj.accepted = True
            invitation_obj.save()
        _ = ConsumerUserCaseRelationship.objects.create(case_id=invitation_obj.case_id,
                                                        domain=invitation_obj.domain,
                                                        case_user_id=consumer_user.id)
        url = reverse('consumer_user:patient_login')
        return HttpResponseRedirect(url)
    else:
        existing_user = False
        try:
            user = User.objects.get(username=email, email=email)
            form = PatientSignUpForm(model_to_dict(user, exclude=['email']))
            existing_user = True
        except User.DoesNotExist:
            form = PatientSignUpForm()
        return render(request, 'signup.html', {'form': form, 'existing_user': existing_user})


@two_factor_exempt
@sensitive_post_parameters('auth-password')
def login_view(request):
    try:
        if request.user and request.user.is_authenticated:
            _ = ConsumerUser.objects.get(user=request.user)
            url = reverse('consumer_user:patient_homepage')
            return HttpResponseRedirect(url)
        if request.method == "POST":
            body = request.POST
            username = body.get('auth-username')
            user = User.objects.get(username=username)
            _ = ConsumerUser.objects.get(user=user)
        return PatientLoginView.as_view()(request)
    except (User.DoesNotExist, ConsumerUser.DoesNotExist):
        return JsonResponse({'message': "Patient User does not exist with your email"}, status=400)


@login_required
def success_view(request):
    return render(request, 'homepage.html')


@login_required
def logout_view(request):
    logout(request)
    url = reverse('consumer_user:patient_login')
    return HttpResponseRedirect(url)


def detail_view(request):
    pass


def delete_view(request):
    pass
