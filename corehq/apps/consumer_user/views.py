import json

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.urls import reverse
from .forms import PatientSignUpForm
from django.views.decorators.debug import sensitive_post_parameters
from two_factor.views import LoginView
from django.shortcuts import render
from corehq.apps.consumer_user.models import ConsumerUser
from corehq.apps.consumer_user.models import ConsumerUserInvitation
from corehq.apps.consumer_user.models import ConsumerUserCaseRelationship
from corehq.apps.domain.decorators import two_factor_exempt
from .decorators import login_required


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
    if request.method == "POST":
        body = request.POST
        entered_email = body.get('email')
        password = body.get('password')
        invitation_obj = None
        consumer_user = None
        try:
            invitation_obj = ConsumerUserInvitation.objects.get(id=invitation)
            if invitation_obj.accepted:
                url = reverse('consumer_user:patient_login')
                return HttpResponseRedirect(url)
            email = invitation_obj.email
            if email != entered_email:
                return JsonResponse({'message': "Email is not same as the one that the invitation has been sent"},
                                    status=400)
            user = User.objects.get(username=email, email=email)
            consumer_user = ConsumerUser.objects.get(user=user)
            login_success = authenticate(request, username=entered_email, password=password)
            if not login_success:
                return JsonResponse({'message': "Existing user but password is different"}, status=400)
        except ConsumerUserInvitation.DoesNotExist:
            return JsonResponse({'message': "Invalid invitation"}, status=400)
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
        form = PatientSignUpForm()
        return render(request, 'signup.html', {'form': form})


@two_factor_exempt
@sensitive_post_parameters('auth-password')
def login_view(request):
    try:
        if request.user and request.user.is_authenticated:
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
    return HttpResponse("Login Success.Username: " + request.user.username, status=200)


def detail_view(request):
    pass


def delete_view(request):
    pass
