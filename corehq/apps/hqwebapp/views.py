from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import login as django_login
from django.contrib.auth.views import logout as django_logout
from django.http import HttpResponseRedirect, HttpResponse, Http404,\
    HttpResponseServerError, HttpResponseNotFound
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm

from dimagi.utils.web import render_to_response
from django.core.urlresolvers import reverse
from corehq.apps.domain.models import Domain
from django.template import loader
from django.template.context import RequestContext


def server_error(request, template_name='500.html'):
    """
    500 error handler.
    """
    # hat tip: http://www.arthurkoziel.com/2009/01/15/passing-mediaurl-djangos-500-error-view/
    t = loader.get_template(template_name) 
    return HttpResponseServerError(t.render(RequestContext(request, 
                                                           {'MEDIA_URL': settings.MEDIA_URL,
                                                            'STATIC_URL': settings.STATIC_URL
                                                            })))
    
def not_found(request, template_name='404.html'):
    """
    404 error handler.
    """
    t = loader.get_template(template_name) 
    return HttpResponseNotFound(t.render(RequestContext(request, 
                                                        {'MEDIA_URL': settings.MEDIA_URL,
                                                         'STATIC_URL': settings.STATIC_URL
                                                        })))
    

def redirect_to_default(req, domain=None):
    if not req.user.is_authenticated():
        #when we want to go live, replace this
        url = reverse('corehq.apps.hqwebapp.views.landing_page')
    else:
        if domain:
            domains = Domain.objects.filter(name=domain)
        else:
            domains = Domain.active_for_user(req.user)
        if   0 == domains.count() and not req.user.is_superuser:
            return render_to_response(req, "hqwebapp/no_permission.html", {})
        elif 1 == domains.count():
            #url = reverse('corehq.apps.app_manager.views.default', args=[domains[0].name])
            url = reverse('corehq.apps.reports.views.default', args=[domains[0].name])
        else:
            url = settings.DOMAIN_SELECT_URL
    return HttpResponseRedirect(url)


def landing_page(req, template_name="home.html"):
    # this view, and the one below, is overridden because
    # we need to set the base template to use somewhere
    # somewhere that the login page can access it.
    if req.user.is_authenticated():
        return HttpResponseRedirect(reverse('homepage'))
    req.base_template = settings.BASE_TEMPLATE
    return django_login(req, template_name=template_name, authentication_form=EmailAuthenticationForm)
    
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
    template_name="hqwebapp/no_permission.html"
    return render_to_response(request, template_name, {})

def login(req, template_name="login_and_password/login.html"):
    # this view, and the one below, is overridden because
    # we need to set the base template to use somewhere
    # somewhere that the login page can access it.
    if req.user.is_authenticated():
        return HttpResponseRedirect(reverse('homepage'))
    req.base_template = settings.BASE_TEMPLATE
    return django_login(req, template_name=template_name, authentication_form=EmailAuthenticationForm)

def logout(req, template_name="hqwebapp/loggedout.html"):
    req.base_template = settings.BASE_TEMPLATE
    response = django_logout(req, **{"template_name" : template_name})
    return HttpResponseRedirect(reverse('login'))

