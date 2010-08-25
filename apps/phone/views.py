from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from corehq.shared_code.webutils import render_to_response

from phone.forms import UserForm, UserSelectionForm
from phone.models import Phone, PhoneBackup, PhoneUserInfo
from phone.registration import get_django_user_object
from corehq.apps.domain.decorators import login_and_domain_required

@login_and_domain_required
def index(request):
    """The root view, a list of phones and linked users"""
    phones = Phone.objects.filter(domain=request.user.selected_domain).select_related(depth=3)
    return render_to_response(request, "phone/phone_index.html", {"phones": phones})

@login_and_domain_required
def single_phone(request, phone_id):
    """Single phone view"""
    phone = get_object_or_404(Phone, id=phone_id, domain=request.user.selected_domain)
    return render_to_response(request, "phone/single_phone.html", {"phone": phone})

@login_and_domain_required
def single_user(request, user_id):
    """Single phone user view"""
    phone_user = get_object_or_404(PhoneUserInfo, id=user_id, phone__domain=request.user.selected_domain)
    return render_to_response(request, "phone/single_phone_user.html", {"phone_user": phone_user})

@login_and_domain_required
def single_django_user(request, user_id):
    django_user = get_object_or_404(User, id=user_id, domain_membership__domain=request.user.selected_domain)
    return render_to_response(request, "phone/single_django_user.html", {"django_user": django_user})

@login_and_domain_required
def create_user(request, user_id):
    """Create a django user from a phone user."""
    phone_user = get_object_or_404(PhoneUserInfo, id=user_id, phone__domain=request.user.selected_domain)
    if request.method == "POST":
        user_form = UserForm(request.POST)
        if user_form.is_valid():
            if phone_user.user:
                # the user was already set
                raise Exception("Sorry, that user has already been created!")
            dummy_user = user_form.save(commit=False)
            phone_user.password = dummy_user.password
            django_user = get_django_user_object(phone_user)
            django_user.username = dummy_user.username
            django_user.save()
            request.user.selected_domain.add(django_user)
            phone_user.user = django_user
            phone_user.status = "site_edited"
            phone_user.save()
            return HttpResponseRedirect(reverse('single_user', kwargs={"user_id": phone_user.id}))   
    else: 
        django_user = get_django_user_object(phone_user)
        django_user.password = "changeme"
        user_form = UserForm(instance=django_user)
    return render_to_response(request, "phone/new_django_user_from_phone.html", 
                              {"phone_user": phone_user,
                               "django_user": django_user,
                               "user_form": user_form})

@login_and_domain_required
def link_user(request, user_id):
    """Link a phone to an existing django user."""
    phone_user = get_object_or_404(PhoneUserInfo, id=user_id, phone__domain=request.user.selected_domain)
    if request.method == "POST":
        user_selection_form = UserSelectionForm(request.user.selected_domain, request.POST)
        if user_selection_form.is_valid():
            user = user_selection_form.cleaned_data["user"]
            phone_user.user = user
            phone_user.status = "site_edited"
            phone_user.save()
            return HttpResponseRedirect(reverse('single_user', kwargs={"user_id": phone_user.id}))
    else: 
        user_selection_form = UserSelectionForm(domain=request.user.selected_domain)
    return render_to_response(request, "phone/link_django_user_from_phone.html", 
                              {"phone_user": phone_user,
                               "user_selection_form": user_selection_form })

@login_and_domain_required
def delete_user(request, user_id):
    phone_user = get_object_or_404(PhoneUserInfo, id=user_id, phone__domain=request.user.selected_domain)

    phone_user.delete()
    
    if phone_user.user is not None:
        PhoneUserInfo.objects.filter(user=phone_user.user).delete()
        phone_user.user.delete()
        
    return HttpResponseRedirect(reverse('phone_index'))
    
    
def restore(request, backup_id):
    """Get a backup file by id"""
    backup = get_object_or_404(PhoneBackup,id=backup_id)
    response = HttpResponse(mimetype='text/xml')
    response.write(backup.attachment.get_contents()) 
    return response
                               
    