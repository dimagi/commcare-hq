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

def my_account(request, domain, template="users/account.html"):
    return edit(request, domain, template, request.user)

def add(request, domain, template="users/single_user.html"):
    return edit(request, domain, template, None)

def edit(request, domain, template="users/single_user.html", django_user = None):
    """
    Edit a user
    """
    context = {}
    if django_user is None:
        django_user = User()
    couch_user = django_user.get_profile().get_couch_user()
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
    context.update({"form": form, "domain": domain, "couch_user": couch_user })
    return render_to_response(request, template, context)

def my_phone_numbers(request, domain, template="users/phone_numbers.html"):
    return phone_numbers(request, request.couch_user, domain, template)

def phone_numbers(request, couch_user, domain, template="users/phone_numbers.html"):
    context = {}
    if request.method == "POST" and 'id_add_phone_number' in request.POST:
        phone_number = request.POST['id_add_phone_number']
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
    return HttpResponseRedirect(reverse("my_account"))

def my_commcare_accounts(request, domain, template="users/commcare_accounts.html"):
    return edit(request, domain, template, request.user)

