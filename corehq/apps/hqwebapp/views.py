from datetime import datetime
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import login as django_login
from django.contrib.auth.views import logout as django_logout
from django.http import HttpResponseRedirect, HttpResponse, Http404,\
    HttpResponseServerError, HttpResponseNotFound
from django.shortcuts import redirect
from corehq.apps.app_manager.models import get_app, BUG_REPORTS_DOMAIN
from corehq.apps.app_manager.models import import_app
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm

from dimagi.utils.web import render_to_response, get_url_base
from django.core.urlresolvers import reverse
from corehq.apps.domain.models import Domain, OldDomain
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
            domain = normalize_domain_name(domain)
            domains = [Domain.get_by_name(domain)]
        else:
            domains = Domain.active_for_user(req.user)
        if   0 == len(domains) and not req.user.is_superuser:
            return no_permissions(req)
        elif 1 == len(domains):
            if domains[0]:
                url = reverse('corehq.apps.reports.views.default', args=[domains[0].name])
            else:
                raise Http404
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
    return redirect('registration_domain')

def login(req, template_name="login_and_password/login.html"):
    # this view, and the one below, is overridden because
    # we need to set the base template to use somewhere
    # somewhere that the login page can access it.
    if req.user.is_authenticated() and req.method != "POST":
        return HttpResponseRedirect(reverse('homepage'))

    req.base_template = settings.BASE_TEMPLATE
    return django_login(req, template_name=template_name, authentication_form=EmailAuthenticationForm)

def logout(req, template_name="hqwebapp/loggedout.html"):
    req.base_template = settings.BASE_TEMPLATE
    response = django_logout(req, **{"template_name" : template_name})
    return HttpResponseRedirect(reverse('login'))

def bug_report(req):
    report = dict([(key, req.POST.get(key, '')) for key in (
        'subject',
        'username',
        'domain',
        'url',
        'now',
        'when',
        'message',
        'app_id',
    )])

    report['datetime'] = datetime.utcnow()

    report['time_description'] = u'just now' if report['now'] else u'earlier: {when}'.format(**report)
    if report['app_id']:
        app = import_app(report['app_id'], BUG_REPORTS_DOMAIN)
        report['copy_url'] = "%s%s" % (get_url_base(), reverse('view_app', args=[BUG_REPORTS_DOMAIN, app.id]))
    else:
        report['copy_url'] = None

    subject = u'CCHQ Bug Report ({domain}): {subject}'.format(**report)
    message = (
        u"username: {username}\n"
        u"domain: {domain}\n"
        u"url: {url}\n"
        u"copy url: {copy_url}\n"
        u"datetime: {datetime}\n"
        u"error occured: {time_description}\n"
        u"Message:\n\n"
        u"{message}\n"
    ).format(**report)

    from django.core.mail.message import EmailMessage
    from django.core.mail import send_mail

    if req.POST.get('five-hundred-report'):
        message = "%s \n\n This messge was reported from a 500 error page! Please fix this ASAP (as if you wouldn't anyway)..." % message
    email = EmailMessage(
        subject,
        message,
        report['username'],
        settings.BUG_REPORT_RECIPIENTS,
        headers = {'Reply-To': report['username']}
    )
    email.send(fail_silently=False)


    if req.POST.get('five-hundred-report'):
        messages.success(req, "Your CommCare HQ Issue Report has been sent. We are working quickly to resolve this problem.")
        return HttpResponseRedirect(reverse('homepage'))

    return HttpResponse()
