from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import login as django_login
from django.contrib.auth.views import logout as django_logout
from django.http import HttpResponseRedirect, HttpResponse
from domain.decorators import login_and_domain_required
from webutils import render_to_response


@login_and_domain_required
def dashboard(request, template_name="hqwebapp/dashboard.html"):
    return render_to_response(request, template_name, 
                              {})

@login_required()
def password_change(req):
    user_to_edit = User.objects.get(id=req.user.id)
    if req.method == 'POST': 
        password_form = AdminPasswordChangeForm(user_to_edit, req.POST)
        if password_form.is_valid():
            password_form.save()
            return HttpResponseRedirect('/')
    else:
        password_form = AdminPasswordChangeForm(user_to_edit)
    template_name="password_change.html"
    return render_to_response(req, template_name, {"form" : password_form})
    
def server_up(req):
    '''View that just returns "success", which can be hooked into server
       monitoring tools like: http://uptime.openacs.org/uptime/'''
    return HttpResponse("success")

def no_permissions(request):
    template_name="hq/no_permission.html"
    return render_to_response(request, template_name, {})

def login(req, template_name="login_and_password/login.html"):
    '''Login to rapidsms'''
    # this view, and the one below, is overridden because 
    # we need to set the base template to use somewhere  
    # somewhere that the login page can access it.
    req.base_template = settings.BASE_TEMPLATE 
    return django_login(req, **{"template_name" : template_name})

def logout(req, template_name="hqwebapp/loggedout.html"):
    '''Logout of rapidsms'''
    req.base_template = settings.BASE_TEMPLATE 
    return django_logout(req, **{"template_name" : template_name})