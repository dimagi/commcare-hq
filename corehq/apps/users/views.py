from django.http import Http404
from django.contrib.auth.models import User
from corehq.util.webutils import render_to_response
from corehq.apps.users.forms import UserForm

def users(req, domain, template="users/users_base.html"):
    return render_to_response(req, template, {
        'domain': domain,
    })

def my_account(request, domain, template="users/single_user.html"):
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
        # TODO: password, phone numbers, commcare users
    context.update({"form": form, "domain": domain })
    return render_to_response(request, template, context)
                               
                                
