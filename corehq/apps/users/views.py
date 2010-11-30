from django.http import Http404
from corehq.util.webutils import render_to_response
from corehq.apps.users.forms import UserForm

def users(req, domain, template="users/users_base.html"):
    return render_to_response(req, template, {
        'domain': domain,
    })

def my_account(request, domain, template="users/single_user.html"):
    return edit(request, domain, request.user.get_profile().get_couch_user().id, template)

def edit(request, domain, user_id, template="users/single_user.html"):
    """
    Edit a user
    """
    context = {}
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            request.user.username = form.cleaned_data['username']
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.email = form.cleaned_data['email']
            request.user.save()
            context['status'] = 'changes saved'
    else:
        form = UserForm()
        form.initial['username'] = request.user.username
        form.initial['first_name'] = request.user.first_name
        form.initial['last_name'] = request.user.last_name
        form.initial['email'] = request.user.email
        # TODO: password, phone numbers, commcare users
    context.update({"form": form, "domain": domain })
    return render_to_response(request, template, context)
                               
                                
