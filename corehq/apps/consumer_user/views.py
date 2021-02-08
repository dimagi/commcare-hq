import json

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.views.decorators.debug import sensitive_post_parameters
from corehq.apps.domain.decorators import two_factor_exempt
from two_factor.views import LoginView
from corehq.apps.consumer_user.models import ConsumerUser, ConsumerUserInvitation
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from .decorators import login_required


def list_view(request):
    pass


@two_factor_exempt
@csrf_exempt
def register_view(request):
    body = json.loads(request.body)

    consumer_invitation_id = body.get('consumer_invitation_id')
    full_name = body.get('full_name')
    password = body.get('password')
    obj = None
    try:
        obj = ConsumerUserInvitation.objects.get(id=consumer_invitation_id)
        if obj.accepted:
            url = reverse('login')
            return HttpResponseRedirect(url)
        email = obj.email
        user = User.objects.get(username=email, email=email)
        _ = ConsumerUser.objects.get(user=user)
        if obj.accepted:
            return JsonResponse({'message': "User already exists"}, status=400)
        else:
            url = reverse('login')
            return HttpResponseRedirect(url)
    except ConsumerUserInvitation.DoesNotExist:
        return JsonResponse({'message': "Invalid invitation"}, status=400)
    except User.DoesNotExist:
        user = User.objects.create_user(username=email, email=email, password=password, first_name=full_name)
        user.save()
    except ConsumerUser.DoesNotExist:
        pass
    consumer_user = ConsumerUser.objects.create(user=user)
    consumer_user.save()
    if obj:
        obj.accepted = True
        obj.save()
    return JsonResponse({'message': "User created successfully"}, status=201)


@two_factor_exempt
@sensitive_post_parameters('auth-password')
@csrf_exempt
def login_view(request):
    try:
        if request.user and request.user.is_authenticated:
            url = reverse('homepage')
            return HttpResponseRedirect(url)
        if request.method == "POST":
            body = json.loads(request.body)
            username = body.get('auth-username')
            password = body.get('auth-password')
            consumer_invitation_id = body.get('consumer_invitation_id')
            user = User.objects.get(username=username)
            _ = ConsumerUser.objects.get(user=user)
            if consumer_invitation_id is not None:
                obj = ConsumerUserInvitation.objects.get(id=consumer_invitation_id)
                obj.accepted = True
                obj.save()
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return JsonResponse({'message': 'Logged in successfully with username = ' + user.username}, status=200)
            else:
                return JsonResponse({'message': 'Invalid credentials'}, status=403)
        return LoginView.as_view()(request)
    except (User.DoesNotExist, ConsumerUser.DoesNotExist):
        return JsonResponse({'message': "Patient User does not exist with your email"}, status=400)


@login_required
def success_view(request):
    return HttpResponse("Login Success.Username: " + request.user.username, status=200)


def detail_view(request):
    pass


def delete_view(request):
    pass
