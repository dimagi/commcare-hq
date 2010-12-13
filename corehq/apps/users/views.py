from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.views.decorators.http import require_POST
from corehq.util.webutils import render_to_response
from corehq.apps.users.forms import UserForm
from corehq.apps.users.models import CouchUser

def users(req, domain, template="users/users_base.html"):
    return render_to_response(req, template, {
        'domain': domain,
    })

def all_users(request, domain, template="users/all_users.html"):
    all_users = CouchUser.view("users/by_domain", key=domain)
    return render_to_response(request, template, {
        'domain': domain,
        'all_users': all_users
    })

def my_account(request, domain, template="users/account.html"):
    return edit(request, domain, request.couch_user.couch_id, template)

def account(request, domain, couch_id, template="users/account.html"):
    return edit(request, domain, couch_id, template)

def my_phone_numbers(request, domain, template="users/phone_numbers.html"):
    return phone_numbers(request, domain, request.couch_user.couch_id, template)

def phone_numbers(request, domain, couch_id, template="users/phone_numbers.html"):
    context = {}
    couch_user = CouchUser.get(couch_id)
    if request.method == "POST" and 'phone_number' in request.POST:
        phone_number = request.POST['phone_number']
        couch_user.add_phone_number(phone_number)
        couch_user.save()
        context['status'] = 'phone number added'
    context['phone_numbers'] = phone_numbers = couch_user.get_phone_numbers()
    context.update({"domain": domain, "couch_user":couch_user })
    return render_to_response(request, template, context)

@require_POST
def delete_phone_number(request, domain, user_id, phone_number):
    user = CouchUser.get(user_id)
    del user.phone_numbers[0]
    user.save()
    return HttpResponseRedirect(reverse("my_phone_numbers", args=(domain, )))

def my_commcare_accounts(request, domain, template="users/commcare_accounts.html"):
    return commcare_accounts(request, domain, request.couch_user.couch_id, template)

def commcare_accounts(request, domain, couch_id, template="users/commcare_accounts.html"):
    context = {}
    couch_user = CouchUser.get(couch_id)
    if request.method == "POST" and 'commcare_user' in request.POST:
        phone_number = request.POST['commcare_user']
        couch_user.add_phone_number(phone_number)
        couch_user.save()
        context['status'] = 'commcare user added'
    # TODO: add a reduce function to that view
    context['other_commcare_users'] = CouchUser.view("users/commcare_users_not_in_hq_user").all()
    context.update({"domain": domain, "couch_user":couch_user })
    return render_to_response(request, template, context)

def edit(request, domain, couch_id=None, template="users/account.html"):
    """
    Edit a user
    """
    context = {}
    if couch_id is None:
        django_user = User()
    else:
        user = CouchUser.get(couch_id)
        django_user = User.objects.get(id=user.django_user.id)
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            django_user.username = form.cleaned_data['username']
            django_user.first_name = form.cleaned_data['first_name']
            django_user.last_name = form.cleaned_data['last_name']
            django_user.email = form.cleaned_data['email']
            django_user.save()
            context['status'] = 'changes saved'
    else:
        form = UserForm()
        form.initial['username'] = django_user.username
        form.initial['first_name'] = django_user.first_name
        form.initial['last_name'] = django_user.last_name
        form.initial['email'] = django_user.email
    couch_user = django_user.get_profile().get_couch_user()
    context.update({"form": form, "domain": domain, "couch_user": couch_user })
    return render_to_response(request, template, context)

