from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import login as django_login, redirect_to_login
from django.contrib.auth.views import logout as django_logout
from django.contrib.sites.models import Site
from django.http import HttpResponseRedirect, HttpResponse, Http404,\
    HttpResponseServerError, HttpResponseNotFound
from django.shortcuts import redirect
from corehq.apps.app_manager.models import BUG_REPORTS_DOMAIN
from corehq.apps.app_manager.models import import_app
from corehq.apps.domain.decorators import require_superuser,\
    login_and_domain_required
from corehq.apps.domain.utils import normalize_domain_name, get_domain_from_url
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm, CloudCareAuthenticationForm
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from dimagi.utils.logging import notify_exception

from dimagi.utils.web import render_to_response, get_url_base
from django.core.urlresolvers import reverse
from corehq.apps.domain.models import Domain
from django.core.mail.message import EmailMessage
from django.template import loader
from django.template.context import RequestContext
from couchforms.models import XFormInstance
from soil import heartbeat
from soil import views as soil_views
import os

def server_error(request, template_name='500.html'):
    """
    500 error handler.
    """

    domain = get_domain_from_url(request.path) or ''


    # hat tip: http://www.arthurkoziel.com/2009/01/15/passing-mediaurl-djangos-500-error-view/
    t = loader.get_template(template_name)
    return HttpResponseServerError(t.render(RequestContext(request,
        {'MEDIA_URL': settings.MEDIA_URL,
         'STATIC_URL': settings.STATIC_URL,
         'domain': domain
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
        # this actually gets hijacked by the static site, but is necessary
        url = reverse('corehq.apps.hqwebapp.views.landing_page')
    else:
        if domain:
            domain = normalize_domain_name(domain)
            domains = [Domain.get_by_name(domain)]
        else:
            domains = Domain.active_for_user(req.user)
        if   0 == len(domains) and not req.user.is_superuser:
            return redirect('registration_domain')
        elif 1 == len(domains):
            if domains[0]:
                domain = domains[0].name
                if req.couch_user.is_commcare_user():
                    url = reverse("cloudcare_main", args=[domain, ""])
                elif req.couch_user.can_view_reports(domain) or req.couch_user.get_viewable_reports(domain):
                    url = reverse('corehq.apps.reports.views.default', args=[domain])
                else:
                    url = reverse('corehq.apps.app_manager.views.default', args=[domain])
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


def yui_crossdomain(req):
    x_domain = """<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
    <allow-access-from domain="yui.yahooapis.com"/>
    <allow-access-from domain="%s"/>
    <site-control permitted-cross-domain-policies="master-only"/>
</cross-domain-policy>""" % Site.objects.get(id=settings.SITE_ID).domain
    return HttpResponse(x_domain, mimetype="application/xml")


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
    template_name = "password_change.html"
    return render_to_response(req, template_name, {"form": password_form})


def server_up(req):
    '''View that just returns "success", which can be hooked into server
       monitoring tools like: pingdom'''

    try:
        hb = heartbeat.is_alive()
    except:
        hb = False

    #in reality when things go wrong with couch and postgres (as of this
    # writing) - it's far from graceful, so this will # likely never be
    # reached because another exception will fire first - but for
    # completeness  sake, this check is done  here to verify our calls will
    # work, and if other error handling allows the request to get this far.

    ## check django db
    try:
        user_count = User.objects.count()
    except:
        user_count = None

    ## check couch
    try:
        xforms = XFormInstance.view('couchforms/by_user', limit=1).all()
    except:
        xforms = None

    if hb and isinstance(user_count, int) and isinstance(xforms, list):
        return HttpResponse("success")
    else:
        message = ['Problems with HQ (%s):' % os.uname()[1]]
        if not hb:
            message.append(' * Celery and or celerybeat is down')
        if user_count is None:
            message.append(' * postgres has issues')
        if xforms is None:
            message.append(' * couch has issues')
        return HttpResponse('\n'.join(message), status=500)


def no_permissions(request, redirect_to=None, template_name="no_permission.html"):
    next = redirect_to or request.GET.get('next', None)
    if request.GET.get('switch', None) == 'true':
        logout(request)
        return redirect_to_login(next or request.path)

    return render_to_response(request, template_name, {'next': next})

def _login(req, domain, template_name):
    if req.user.is_authenticated() and req.method != "POST":
        redirect_to = req.REQUEST.get('next', '')
        if redirect_to:
            return HttpResponseRedirect(redirect_to)
        if not domain:
            return HttpResponseRedirect(reverse('homepage'))
        else:
            return HttpResponseRedirect(reverse('domain_homepage', args=[domain]))

    if req.method == 'POST' and domain and '@' not in req.POST.get('username', '@'):
        req.POST._mutable = True
        req.POST['username'] = format_username(req.POST['username'], domain)
        req.POST._mutable = False
    
    req.base_template = settings.BASE_TEMPLATE
    return django_login(req, template_name=template_name,
                        authentication_form=EmailAuthenticationForm if not domain else CloudCareAuthenticationForm,
                        extra_context={'domain': domain})
    
def login(req, template_name="login_and_password/login.html"):
    # this view, and the one below, is overridden because
    # we need to set the base template to use somewhere
    # somewhere that the login page can access it.
    domain = req.REQUEST.get('domain', None)
    return _login(req, domain, template_name)
    
def domain_login(req, domain, template_name="login_and_password/login.html"):
    return _login(req, domain, template_name)

def logout(req, template_name="hqwebapp/loggedout.html"):
    req.base_template = settings.BASE_TEMPLATE
    response = django_logout(req, **{"template_name": template_name})
    return HttpResponseRedirect(reverse('login'))

@login_and_domain_required
def retrieve_download(req, domain, download_id, template="hqwebapp/file_download.html"):
    return soil_views.retrieve_download(req, download_id, template)

@require_superuser
def debug_notify(request):
    try:
        0 / 0
    except ZeroDivisionError:
        notify_exception(request,
            "If you want to achieve a 500-style email-out but don't want the user to see a 500, use notify_exception(request[, message])")
    return HttpResponse("Email should have been sent")


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

    report['user_agent'] = req.META['HTTP_USER_AGENT']
    report['datetime'] = datetime.utcnow()

    report['time_description'] = u'just now' if report['now'] else u'earlier: {when}'.format(**report)
    if report['app_id']:
        app = import_app(report['app_id'], BUG_REPORTS_DOMAIN)
        report['copy_url'] = "%s%s" % (get_url_base(), reverse('view_app', args=[BUG_REPORTS_DOMAIN, app.id]))
    else:
        report['copy_url'] = None

    try:
        couch_user = CouchUser.get_by_username(report['username'])
        full_name = couch_user.full_name
    except Exception:
        full_name = None
    report['full_name'] = full_name

    subject = u'{subject} ({domain})'.format(**report)
    message = (
        u"username: {username}\n"
        u"full name: {full_name}\n"
        u"domain: {domain}\n"
        u"url: {url}\n"
        u"copy url: {copy_url}\n"
        u"datetime: {datetime}\n"
        u"error occured: {time_description}\n"
        u"User Agent: {user_agent}\n"
        u"Message:\n\n"
        u"{message}\n"
        ).format(**report)

    if full_name and not any([c in full_name for c in '<>"']):
        reply_to = '"{full_name}" <{username}>'.format(**report)
    else:
        reply_to = report['username']

    # if the person looks like a commcare user, fogbugz can't reply
    # to their email, so just use the default
    if settings.HQ_ACCOUNT_ROOT in reply_to:
        reply_to = settings.EMAIL_HOST_USER

    if req.POST.get('five-hundred-report'):
        message = "%s \n\n This messge was reported from a 500 error page! Please fix this ASAP (as if you wouldn't anyway)..." % message
    email = EmailMessage(
        subject,
        message,
        report['username'],
        settings.BUG_REPORT_RECIPIENTS,
        headers={'Reply-To': reply_to}
    )
    email.send(fail_silently=False)

    if req.POST.get('five-hundred-report'):
        messages.success(req,
            "Your CommCare HQ Issue Report has been sent. We are working quickly to resolve this problem.")
        return HttpResponseRedirect(reverse('homepage'))

    return HttpResponse()
