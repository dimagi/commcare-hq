import functools
import json
import logging
import os
import re
import sys
import traceback
import uuid
from datetime import datetime
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView
from django.core import cache
from django.core.mail.message import EmailMessage
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import redirect, render
from django.template import loader
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import resolve
from django.utils import html
from django.utils.decorators import method_decorator
from django.utils.translation import LANGUAGE_SESSION_KEY
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView
from django.views.generic.base import View

import httpagentparser
import requests
from couchdbkit import ResourceNotFound
from memoized import memoized
from sentry_sdk import last_event_id
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm
from two_factor.views import LoginView

from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.util.metrics import create_metrics_event, metrics_counter, metrics_gauge
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from dimagi.utils.couch.database import get_db
from dimagi.utils.django.email import COMMCARE_MESSAGE_ID_HEADER
from dimagi.utils.django.request import mutable_querydict
from dimagi.utils.logging import notify_exception, notify_error
from dimagi.utils.web import get_site_domain, get_url_base, json_response
from soil import DownloadBase
from soil import views as soil_views

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.decorators import (
    always_allow_project_access,
)
from corehq.apps.analytics import ab_tests
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    require_superuser,
    track_domain_request,
    two_factor_exempt,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import get_domain_from_url, normalize_domain_name
from corehq.apps.dropbox.decorators import require_dropbox_session
from corehq.apps.dropbox.exceptions import (
    DropboxInvalidToken,
    DropboxUploadAlreadyInProgress,
)
from corehq.apps.dropbox.models import DropboxUploadHelper
from corehq.apps.dropbox.views import DROPBOX_ACCESS_TOKEN, DropboxAuthInitiate
from corehq.apps.hqadmin.management.commands.deploy_in_progress import (
    DEPLOY_IN_PROGRESS_FLAG,
)
from corehq.apps.hqadmin.service_checks import CHECKS, run_checks
from corehq.apps.hqwebapp.doc_info import get_doc_info, get_object_info
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.hqwebapp.forms import (
    CloudCareAuthenticationForm,
    EmailAuthenticationForm,
)
from corehq.apps.hqwebapp.login_utils import get_custom_login_page
from corehq.apps.hqwebapp.utils import (
    get_environment_friendly_name,
    update_session_language,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from corehq.apps.sms.models import MessagingEvent, MessagingSubEvent
from corehq.apps.users.landing_pages import (
    get_cloudcare_urlname,
    get_redirect_url,
)
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
)
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.util.context_processors import commcare_hq_names
from corehq.util.metrics.const import TAG_UNKNOWN, MPM_MAX
from corehq.util.metrics.utils import sanitize_url
from corehq.util.view_utils import reverse
from no_exceptions.exceptions import Http403


def is_deploy_in_progress():
    cache = get_redis_default_cache()
    return cache.get(DEPLOY_IN_PROGRESS_FLAG) is not None


def format_traceback_the_way_python_does(type, exc, tb):
    """
    Returns a traceback that looks like the one python gives you in the shell, e.g.

    Traceback (most recent call last):
      File "<stdin>", line 2, in <module>
    NameError: name 'name' is not defined
    """
    tb = ''.join(traceback.format_tb(tb))
    return f'Traceback (most recent call last):\n{tb}{type.__name__}: {exc}'


def server_error(request, template_name='500.html', exception=None):
    """
    500 error handler.
    """
    urlname = resolve(request.path).url_name
    submission_urls = [
        'receiver_secure_post',
        'receiver_secure_post_with_app_id',
        'receiver_post_with_app_id'
    ]
    if urlname in submission_urls + ['app_aware_restore']:
        return HttpResponse(status=500)

    domain = get_domain_from_url(request.path) or ''

    # hat tip: http://www.arthurkoziel.com/2009/01/15/passing-mediaurl-djangos-500-error-view/
    t = loader.get_template(template_name)
    type, exc, tb = sys.exc_info()

    traceback_text = format_traceback_the_way_python_does(type, exc, tb)
    traceback_key = uuid.uuid4().hex
    cache.cache.set(traceback_key, traceback_text, 60*60)

    if settings.UNIT_TESTING:
        # Explicitly don't render the 500 page during unit tests to prevent
        # obfuscating errors in templatetags / context processor. More context here:
        # https://github.com/dimagi/commcare-hq/pull/25835#discussion_r343997006
        return HttpResponse(status=500)

    return HttpResponseServerError(t.render(
        context={
            'MEDIA_URL': settings.MEDIA_URL,
            'STATIC_URL': settings.STATIC_URL,
            'domain': domain,
            '500traceback': traceback_key,
            'sentry_event_id': last_event_id(),
        },
        request=request,
    ))


def not_found(request, template_name='404.html', exception=None):
    """
    404 error handler.
    """
    t = loader.get_template(template_name)
    return HttpResponseNotFound(t.render(
        context={
            'MEDIA_URL': settings.MEDIA_URL,
            'STATIC_URL': settings.STATIC_URL,
        },
        request=request,
    ))


@require_GET
@location_safe
@always_allow_project_access
def redirect_to_default(req, domain=None):
    if not req.user.is_authenticated:
        if domain != None:
            url = reverse('domain_login', args=[domain])
        else:
            url = reverse('login')
    elif domain and _two_factor_needed(domain, req):
        return TemplateResponse(
            request=req,
            template='two_factor/core/otp_required.html',
            status=403,
        )
    else:
        if domain:
            domain = normalize_domain_name(domain)
            domains = [Domain.get_by_name(domain)]
        else:
            domains = Domain.active_for_user(req.user)

        if 0 == len(domains) and not req.user.is_superuser:
            return redirect('registration_domain')
        elif 1 == len(domains):
            from corehq.apps.users.models import DomainMembershipError
            if domains[0]:
                domain = domains[0].name
                couch_user = req.couch_user
                try:
                    role = couch_user.get_role(domain)
                except DomainMembershipError:
                    # commcare users without roles should always be denied access
                    if couch_user.is_commcare_user():
                        raise Http404()
                    else:
                        # web users without roles are redirected to the dashboard default
                        # view since some domains allow web users to request access if they
                        # don't have it
                        url = reverse("dashboard_domain", args=[domain])
                else:
                    if role and role.default_landing_page:
                        url = get_redirect_url(role.default_landing_page, domain)
                    elif couch_user.is_commcare_user():
                        url = reverse(get_cloudcare_urlname(domain), args=[domain])
                    else:
                        url = reverse("dashboard_domain", args=[domain])
            else:
                raise Http404()
        else:
            url = settings.DOMAIN_SELECT_URL
    return HttpResponseRedirect(url)


def _two_factor_needed(domain_name, request):
    domain_name = normalize_domain_name(domain_name)
    domain_obj = Domain.get_by_name(domain_name)
    if domain_obj:
        return (
            domain_obj.two_factor_auth
            and not request.couch_user.two_factor_disabled
            and not request.user.is_verified()
        )


def yui_crossdomain(req):
    x_domain = """<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
    <allow-access-from domain="yui.yahooapis.com"/>
    <allow-access-from domain="%s"/>
    <site-control permitted-cross-domain-policies="master-only"/>
</cross-domain-policy>""" % get_site_domain()
    return HttpResponse(x_domain, content_type="application/xml")


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
    return render(req, template_name, {"form": password_form})


def server_up(req):
    """
    Health check view which can be hooked into server monitoring tools like 'pingdom'

    Returns:
        HttpResponse("success", status_code=200)
        HttpResponse(error_message, status_code=500)

    Hit serverup.txt to check all the default enabled services (always_check=True)
    Hit serverup.txt?only={check_name} to only check a specific service
    Hit serverup.txt?{check_name} to include a non-default check (currently only ``heartbeat``)
    """
    only = req.GET.get('only', None)
    if only and only in CHECKS:
        checks_to_do = [only]
    else:
        checks_to_do = [
            check
            for check, check_info in CHECKS.items()
            if check_info['always_check'] or req.GET.get(check, None) is not None
        ]

    statuses = run_checks(checks_to_do)
    failed_checks = [(check, status) for check, status in statuses if not status.success]

    for check_name, status in statuses:
        tags = {
            'status': 'failed' if not status.success else 'ok',
            'check': check_name
        }
        metrics_gauge('commcare.serverup.check', status.duration, tags=tags, multiprocess_mode=MPM_MAX)

    if failed_checks and not is_deploy_in_progress():
        status_messages = [
            html.linebreaks('<strong>{}</strong>: {}'.format(check, html.escape(status.msg)).strip())
            for check, status in failed_checks
        ]
        create_metrics_event(
            'Serverup check failed', '\n'.join(status_messages),
            alert_type='error', aggregation_key='serverup',
        )
        status_messages.insert(0, 'Failed Checks (%s):' % os.uname()[1])
        return HttpResponse(''.join(status_messages), status=500)
    else:
        return HttpResponse("success")


def _no_permissions_message(request, template_name="403.html", message=None):
    t = loader.get_template(template_name)
    return t.render(
        context={
            'MEDIA_URL': settings.MEDIA_URL,
            'STATIC_URL': settings.STATIC_URL,
            'message': message,
        },
        request=request,
    )


def no_permissions(request, redirect_to=None, template_name="403.html", message=None, exception=None):
    """
    403 error handler.
    """
    return HttpResponseForbidden(_no_permissions_message(request, template_name, message))


def no_permissions_exception(request, template_name="403.html", message=None):
    return Http403(_no_permissions_message(request, template_name, message))


def csrf_failure(request, reason=None, template_name="csrf_failure.html"):
    t = loader.get_template(template_name)
    return HttpResponseForbidden(t.render(
        context={
            'MEDIA_URL': settings.MEDIA_URL,
            'STATIC_URL': settings.STATIC_URL,
        },
        request=request,
    ))


@sensitive_post_parameters('auth-password')
def _login(req, domain_name, custom_login_page, extra_context=None):
    extra_context = extra_context or {}
    if req.user.is_authenticated and req.method == "GET":
        redirect_to = req.GET.get('next', '')
        if redirect_to:
            return HttpResponseRedirect(redirect_to)
        if not domain_name:
            return HttpResponseRedirect(reverse('homepage'))
        else:
            return HttpResponseRedirect(reverse('domain_homepage', args=[domain_name]))

    if req.method == 'POST' and domain_name and '@' not in req.POST.get('auth-username', '@'):
        with mutable_querydict(req.POST):
            req.POST['auth-username'] = format_username(req.POST['auth-username'], domain_name)

    if 'auth-username' in req.POST:
        couch_user = CouchUser.get_by_username(req.POST['auth-username'].lower())
        if couch_user:
            new_lang = couch_user.language
            old_lang = req.session.get(LANGUAGE_SESSION_KEY)
            update_session_language(req, old_lang, new_lang)

    req.base_template = settings.BASE_TEMPLATE

    context = {}
    template_name = custom_login_page if custom_login_page else 'login_and_password/login.html'
    if not custom_login_page and domain_name:
        domain_obj = Domain.get_by_name(domain_name)
        req_params = req.GET if req.method == 'GET' else req.POST
        context.update({
            'domain': domain_name,
            'hr_name': domain_obj.display_name(),
            'next': req_params.get('next', '/a/%s/' % domain_name),
            'allow_domain_requests': domain_obj.allow_domain_requests,
            'current_page': {'page_name': _('Welcome back to %s!') % domain_obj.display_name()},
        })
    else:
        commcare_hq_name = commcare_hq_names(req)['commcare_hq_names']["COMMCARE_HQ_NAME"]
        context.update({
            'current_page': {'page_name': _('Welcome back to %s!') % commcare_hq_name},
        })
    if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
        auth_view = CloudCareLoginView
    else:
        auth_view = HQLoginView if not domain_name else CloudCareLoginView

    demo_workflow_ab_v2 = ab_tests.SessionAbTest(ab_tests.DEMO_WORKFLOW_V2, req)

    if settings.IS_SAAS_ENVIRONMENT:
        context['demo_workflow_ab_v2'] = demo_workflow_ab_v2.context

    context.update(extra_context)
    response = auth_view.as_view(template_name=template_name, extra_context=context)(req)

    if settings.IS_SAAS_ENVIRONMENT:
        demo_workflow_ab_v2.update_response(response)

    return response


@two_factor_exempt
@sensitive_post_parameters('auth-password')
def login(req):
    # This is a wrapper around the _login view

    if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
        login_url = reverse('domain_login', kwargs={'domain': 'icds-cas'})
        return HttpResponseRedirect(login_url)

    req_params = req.GET if req.method == 'GET' else req.POST
    domain = req_params.get('domain', None)
    return _login(req, domain, get_custom_login_page(req.get_host()))


@location_safe
def domain_login(req, domain, custom_template_name=None, extra_context=None):
    # This is a wrapper around the _login view which sets a different template
    project = Domain.get_by_name(domain)
    if not project:
        raise Http404

    # FYI, the domain context_processor will pick this up and apply the
    # necessary domain contexts:
    req.project = project
    if custom_template_name is None:
        custom_template_name = get_custom_login_page(req.get_host())
    return _login(req, domain, custom_template_name, extra_context)


@location_safe
def iframe_domain_login(req, domain):
    return domain_login(req, domain, custom_template_name="hqwebapp/iframe_domain_login.html", extra_context={
        'current_page': {'page_name': _('Your session has expired')},
    })


class HQLoginView(LoginView):
    form_list = [
        ('auth', EmailAuthenticationForm),
        ('token', AuthenticationTokenForm),
        ('backup', BackupTokenForm),
    ]
    extra_context = {}

    def get_context_data(self, **kwargs):
        context = super(HQLoginView, self).get_context_data(**kwargs)
        context.update(self.extra_context)
        context['implement_password_obfuscation'] = settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE
        return context


class CloudCareLoginView(HQLoginView):
    form_list = [
        ('auth', CloudCareAuthenticationForm),
        ('token', AuthenticationTokenForm),
        ('backup', BackupTokenForm),
    ]


@two_factor_exempt
def logout(req, default_domain_redirect='domain_login'):
    referer = req.META.get('HTTP_REFERER')
    domain = get_domain_from_url(urlparse(referer).path) if referer else None

    # we don't actually do anything with the response here:
    LogoutView.as_view(template_name=settings.BASE_TEMPLATE)(req)

    if referer and domain:
        domain_login_url = reverse(default_domain_redirect, kwargs={'domain': domain})
        return HttpResponseRedirect('%s' % domain_login_url)
    else:
        return HttpResponseRedirect(reverse('login'))


# ping_response powers the ping_login and ping_session views, both tiny views used in user inactivity and
# session expiration handling.ping_session extends the user's current session, while ping_login does not.
# This difference is controlled in SelectiveSessionMiddleware, which makes ping_login bypass sessions.
@location_safe
@two_factor_exempt
def ping_response(request):
    return JsonResponse({
        'success': request.user.is_authenticated,
        'session_expiry': request.session.get('session_expiry'),
        'secure_session': request.session.get('secure_session'),
        'secure_session_timeout': request.session.get('secure_session_timeout'),
        'username': request.user.username,
    })


@location_safe
@login_required
def login_new_window(request):
    return render_static(request, "hqwebapp/close_window.html", _("Thank you for logging in!"))


@location_safe
@login_required
def iframe_domain_login_new_window(request):
    return TemplateView.as_view(template_name='hqwebapp/iframe_close_window.html')(request)


@login_and_domain_required
@track_domain_request(calculated_prop='cp_n_downloads_custom_exports')
def retrieve_download(req, domain, download_id, template="hqwebapp/includes/file_download.html"):
    next_url = req.GET.get('next', reverse('my_project_settings', args=[domain]))
    return soil_views.retrieve_download(req, download_id, template,
                                        extra_context={'domain': domain, 'next_url': next_url})


def dropbox_next_url(request, download_id):
    return request.META.get('HTTP_REFERER', '/')


@login_required
@require_dropbox_session(next_url=dropbox_next_url)
def dropbox_upload(request, download_id):
    download = DownloadBase.get(download_id)
    if download is None:
        logging.error("Download file request for expired/nonexistent file requested")
        raise Http404
    else:
        filename = download.get_filename()
        # Hack to get target filename from content disposition
        match = re.search('filename="([^"]*)"', download.content_disposition)
        dest = match.group(1) if match else 'download.txt'

        try:
            uploader = DropboxUploadHelper.create(
                request.session.get(DROPBOX_ACCESS_TOKEN),
                src=filename,
                dest=dest,
                download_id=download_id,
                user=request.user,
            )
        except DropboxInvalidToken:
            return HttpResponseRedirect(reverse(DropboxAuthInitiate.slug))
        except DropboxUploadAlreadyInProgress:
            uploader = DropboxUploadHelper.objects.get(download_id=download_id)
            messages.warning(
                request,
                'The file is in the process of being synced to dropbox! It is {0:.2f}% '
                'complete.'.format(uploader.progress * 100)
            )
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        uploader.upload()

        messages.success(
            request,
            _("Apps/{app}/{dest} is queued to sync to dropbox! You will receive an email when it"
                " completes.".format(app=settings.DROPBOX_APP_NAME, dest=dest))
        )

    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


@require_superuser
def debug_notify(request):
    try:
        0 // 0
    except ZeroDivisionError:
        notify_exception(request,
            "If you want to achieve a 500-style email-out but don't want the user to see a 500, use notify_exception(request[, message])")
    return HttpResponse("Email should have been sent")


@waf_allow('XSS_BODY')
@require_POST
def jserror(request):
    agent = request.META.get('HTTP_USER_AGENT', None)
    os = browser_name = browser_version = bot = TAG_UNKNOWN
    if agent:
        parsed_agent = httpagentparser.detect(agent)
        bot = parsed_agent.get('bot', False)
        if 'os' in parsed_agent:
            os = parsed_agent['os'].get('name', TAG_UNKNOWN)

        if 'browser' in parsed_agent:
            browser_version = parsed_agent['browser'].get('version', TAG_UNKNOWN)
            browser_name = parsed_agent['browser'].get('name', TAG_UNKNOWN)

    url = request.POST.get('page', None)
    domain = None
    if url:
        path = urlparse(url).path
        if path:
            domain = get_domain_from_url(path)
    domain = domain or '_unknown'

    metrics_counter('commcare.jserror.count', tags={
        'os': os,
        'browser_version': browser_version,
        'browser_name': browser_name,
        'url': sanitize_url(url),
        'bot': bot,
        'domain': domain,
    })

    notify_error(message=f'[JS] {request.POST.get("message")}', details={
        'message': request.POST.get('message'),
        'domain': domain,
        'page': url,
        'file': request.POST.get('file'),
        'line': request.POST.get('line'),
        'stack': request.POST.get('stack'),
        'meta': {
            'os': os,
            'browser_version': browser_version,
            'browser_name': browser_name,
            'bot': bot,
        }
    })

    return HttpResponse('')


@method_decorator([login_required], name='dispatch')
class BugReportView(View):
    def post(self, req, *args, **kwargs):
        email = self._get_email_message(
            post_params=req.POST,
            couch_user=req.couch_user,
            uploaded_file=req.FILES.get('report_issue')
        )

        email.send(fail_silently=False)

        if req.POST.get('five-hundred-report'):
            messages.success(
                req,
                _("Your CommCare HQ Issue Report has been sent. We are working quickly to resolve this problem.")
            )
            return HttpResponseRedirect(reverse('homepage'))

        return HttpResponse()

    @staticmethod
    def _get_email_message(post_params, couch_user, uploaded_file):
        report = dict([(key, post_params.get(key, '')) for key in (
            'subject',
            'username',
            'domain',
            'url',
            'message',
            'app_id',
            'cc',
            'email',
            '500traceback',
            'sentry_id',
        )])

        try:
            full_name = couch_user.full_name
            if couch_user.is_commcare_user():
                email = report['email']
            else:
                email = couch_user.get_email()
        except Exception:
            full_name = None
            email = report['email']
        report['full_name'] = full_name
        report['email'] = email or report['username']

        if report['domain']:
            domain = report['domain']
        elif len(couch_user.domains) == 1:
            # This isn't a domain page, but the user has only one domain, so let's use that
            domain = couch_user.domains[0]
        else:
            domain = "<no domain>"

        other_recipients = [el.strip() for el in report['cc'].split(",") if el]

        message = (
            f"username: {report['username']}\n"
            f"full name: {report['full_name']}\n"
            f"domain: {report['domain']}\n"
            f"url: {report['url']}\n"
            f"recipients: {', '.join(other_recipients)}\n"
        )

        domain_object = Domain.get_by_name(domain) if report['domain'] else None
        debug_context = {
            'datetime': datetime.utcnow(),
            'self_started': '<unknown>',
            'scale_backend': '<unknown>',
            'has_handoff_info': '<unknown>',
            'project_description': '<unknown>',
            'sentry_error': '{}{}'.format(getattr(settings, 'SENTRY_QUERY_URL', ''), report['sentry_id'])
        }
        if domain_object:
            current_project_description = domain_object.project_description if domain_object else None
            new_project_description = post_params.get('project_description')
            if (domain_object and couch_user.is_domain_admin(domain=domain) and new_project_description
                    and current_project_description != new_project_description):
                domain_object.project_description = new_project_description
                domain_object.save()

            message += ((
                "software plan: {software_plan}\n"
            ).format(
                software_plan=Subscription.get_subscribed_plan_by_domain(domain),
            ))

            debug_context.update({
                'self_started': domain_object.internal.self_started,
                'scale_backend': should_use_sql_backend(domain),
                'has_handoff_info': bool(domain_object.internal.partner_contact),
                'project_description': domain_object.project_description,
            })

        subject = '{subject} ({domain})'.format(subject=report['subject'], domain=domain)

        if full_name and not any([c in full_name for c in '<>"']):
            reply_to = '"{full_name}" <{email}>'.format(**report)
        else:
            reply_to = report['email']

        # if the person looks like a commcare user, fogbugz can't reply
        # to their email, so just use the default
        if settings.HQ_ACCOUNT_ROOT in reply_to:
            reply_to = settings.SERVER_EMAIL

        message += "Message:\n\n{message}\n".format(message=report['message'])
        if post_params.get('five-hundred-report'):
            extra_message = ("This message was reported from a 500 error page! "
                             "Please fix this ASAP (as if you wouldn't anyway)...")
            extra_debug_info = (
                "datetime: {datetime}\n"
                "Is self start: {self_started}\n"
                "Is scale backend: {scale_backend}\n"
                "Has Support Hand-off Info: {has_handoff_info}\n"
                "Project description: {project_description}\n"
                "Sentry Error: {sentry_error}\n"
            ).format(**debug_context)
            traceback_info = cache.cache.get(report['500traceback']) or 'No traceback info available'
            cache.cache.delete(report['500traceback'])
            message = "\n\n".join([message, extra_debug_info, extra_message, traceback_info])

        email = EmailMessage(
            subject=subject,
            body=message,
            to=[settings.SUPPORT_EMAIL],
            headers={'Reply-To': reply_to},
            cc=other_recipients
        )

        if uploaded_file:
            filename = uploaded_file.name
            content = uploaded_file.read()
            email.attach(filename=filename, content=content)

        # only fake the from email if it's an @dimagi.com account
        is_icds_env = settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS
        if re.search(r'@dimagi\.com$', report['username']) and not is_icds_env:
            email.from_email = report['username']
        else:
            email.from_email = settings.SUPPORT_EMAIL

        return email


def render_static(request, template, page_name):
    """
    Takes an html file and renders it Commcare HQ's styling
    """
    return render(request, "hqwebapp/blank.html",
                  {'tmpl': template, 'page_name': page_name})


def apache_license(request):
    return render_static(request, "apache_license.html", _("Apache License"))


def bsd_license(request):
    return render_static(request, "bsd_license.html", _("BSD License"))


class BasePageView(TemplateView):
    urlname = None  # name of the view used in urls
    page_title = None  # what shows up in the <title>
    template_name = 'hqwebapp/base_page.html'

    @property
    def page_name(self):
        """
        This is what is visible to the user.
        page_title is what shows up in <title> tags.
        """
        return self.page_title

    @property
    def page_url(self):
        raise NotImplementedError()

    @property
    def parent_pages(self):
        """
        Specify parent pages as a list of
        [{
            'title': <name>,
            'url: <url>,
        }]
        """
        return []

    @property
    def main_context(self):
        """
        The shared context for rendering this page.
        """
        return {
            'current_page': {
                'page_name': self.page_name,
                'title': self.page_title,
                'url': self.page_url,
                'parents': self.parent_pages,
            },
        }

    @property
    def page_context(self):
        """
        The Context for the settings page
        """
        return {}

    def get_context_data(self, **kwargs):
        context = super(BasePageView, self).get_context_data(**kwargs)
        context.update(self.main_context)
        context.update(self.page_context)
        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response with a template rendered with the given context.
        """
        return render(self.request, self.template_name, context)


class BaseSectionPageView(BasePageView):
    section_name = ""
    template_name = "hqwebapp/base_section.html"

    @property
    def section_url(self):
        raise NotImplementedError

    @property
    def main_context(self):
        context = super(BaseSectionPageView, self).main_context
        context.update({
            'section': {
                'page_name': self.section_name,
                'url': self.section_url,
            }
        })
        return context


class PaginatedItemException(Exception):
    pass


class CRUDPaginatedViewMixin(object):
    """
    Mix this in with a TemplateView view object.
    For usage tips, see the docs for UI Helpers > Paginated CRUD View.
    """
    DEFAULT_LIMIT = 10

    limit_text = ugettext_noop("items per page")
    empty_notification = ugettext_noop("You have no items.")
    loading_message = ugettext_noop("Loading...")
    deleted_items_header = ugettext_noop("Deleted Items:")
    new_items_header = ugettext_noop("New Items:")

    def _safe_escape(self, expression, default):
        try:
            return expression()
        except ValueError:
            return default

    @property
    def parameters(self):
        """
        Specify GET or POST from a request object.
        """
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def page(self):
        return self._safe_escape(
            lambda: int(self.parameters.get('page', 1)),
            1
        )

    @property
    @memoized
    def limit(self):
        return self._safe_escape(
            lambda: int(self.parameters.get('limit', self.DEFAULT_LIMIT)),
            self.DEFAULT_LIMIT
        )

    @property
    def total(self):
        raise NotImplementedError("You must implement total.")

    @property
    def sort_by(self):
        return self.parameters.GET.get('sortBy', 'abc')

    @property
    def skip(self):
        return (self.page - 1) * self.limit

    @property
    def action(self):
        action = self.parameters.get('action')
        if action not in self.allowed_actions:
            raise Http404()
        return action

    @property
    def column_names(self):
        raise NotImplementedError("you must return a list of column names")

    @property
    def pagination_context(self):
        create_form = self.get_create_form()
        return {
            'pagination': {
                'page': self.page,
                'limit': self.limit,
                'total': self.total,
                'limit_options': list(range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT)),
                'column_names': self.column_names,
                'num_columns': len(self.column_names),
                'text': {
                    'limit': self.limit_text,
                    'empty': self.empty_notification,
                    'loading': self.loading_message,
                    'deleted_items': self.deleted_items_header,
                    'new_items': self.new_items_header,
                },
                'create_item_form': self.get_create_form_response(create_form) if create_form else None,
                'create_item_form_class': self.create_item_form_class,
            }
        }

    @property
    def allowed_actions(self):
        return [
            'create',
            'update',
            'delete',
            'paginate',
            'refresh',
        ]

    @property
    def paginate_crud_response(self):
        """
        Return this in the post method of your view class.
        """
        response = getattr(self, '%s_response' % self.action)
        return HttpResponse(json.dumps(response, cls=LazyEncoder))

    @property
    def create_response(self):
        create_form = self.get_create_form()
        new_item = None
        if create_form.is_valid():
            new_item = self.get_create_item_data(create_form)
            create_form = self.get_create_form(is_blank=True)
        return {
            'newItem': new_item,
            'form': self.get_create_form_response(create_form)
        }

    @property
    def update_response(self):
        update_form = self.get_update_form()
        updated_item = None
        if update_form.is_valid():
            updated_item = self.get_updated_item_data(update_form)
        return {
            'updatedItem': updated_item,
            'form': self.get_update_form_response(update_form),
        }

    @property
    def refresh_response(self):
        try:
            self.refresh_item(self.item_id)
        except PaginatedItemException as e:
            return {
                'error': _("<strong>Problem Refreshing List:</strong> %s") % e,
            }
        return {
            'success': True,
            'currentPage': self.page,
            'total': self.total,
            'paginatedList': list(self.paginated_list),
        }

    @property
    def delete_response(self):
        try:
            response = self.get_deleted_item_data(self.item_id)
            return {
                'deletedItem': response
            }
        except PaginatedItemException as e:
            return {
                'error': _("<strong>Problem Deleting:</strong> %s") % e,
            }

    @property
    def item_id(self):
        try:
            return self.parameters['itemId']
        except KeyError:
            raise PaginatedItemException(_("The item's ID was not passed to the server."))

    @property
    def paginate_response(self):
        return {
            'success': True,
            'currentPage': self.page,
            'total': self.total,
            'paginatedList': list(self.paginated_list),
        }

    @property
    def paginated_list(self):
        """
        This should return a list (or generator object) of data formatted as follows:
        [
            {
                'itemData': {
                    'id': <id of item>,
                    <json dict of item data for the knockout model to use>
                },
                'template': <knockout template id>
            }
        ]
        """
        raise NotImplementedError("Return a list of data for the request response.")

    def get_create_form(self, is_blank=False):
        """
        This should be a crispy form that creates an item.
        It's not required if you just want a paginated view.
        """
        pass

    create_item_form_class = 'form form-inline'

    def get_create_form_response(self, create_form):
        return render_to_string(
            'hqwebapp/includes/create_item_form.html', {
                'form': create_form
            }
        )

    def get_update_form(self, initial_data=None):
        raise NotImplementedError("You must return a form object that will update an Item")

    def get_update_form_response(self, update_form):
        return render_to_string(
            'hqwebapp/partials/update_item_form.html', {
                'form': update_form
            }
        )

    def refresh_item(self, item_id):
        """
        Process the item that triggered a list refresh here.
        """
        raise NotImplementedError("You must implement refresh_item")

    def get_create_item_data(self, create_form):
        """
        This should return a dict of data for the created item.
        {
            'itemData': {
                'id': <id of item>,
                <json dict of item data for the knockout model to use>
            },
            'template': <knockout template id>
        }
        """
        raise NotImplementedError("You must implement get_new_item_data")

    def get_updated_item_data(self, update_form):
        """
        This should return a dict of data for the updated item.
        {
            'itemData': {
                'id': <id of item>,
                <json dict of item data for the knockout model to use>
            },
            'template': <knockout template id>
        }
        """
        raise NotImplementedError("You must implement get_updated_item_data")

    def get_deleted_item_data(self, item_id):
        """
        This should return a dict of data for the deleted item.
        {
            'itemData': {
                'id': <id of item>,
                <json dict of item data for the knockout model to use>
            },
            'template': <knockout template id>
        }
        """
        raise NotImplementedError("You must implement get_deleted_item_data")


@login_required
def quick_find(request):
    query = request.GET.get('q')
    redirect = request.GET.get('redirect') != 'false'
    if not query:
        return HttpResponseBadRequest('GET param "q" must be provided')

    def deal_with_doc(doc, domain, doc_info_fn):
        is_member = domain and request.couch_user.is_member_of(domain, allow_mirroring=True)
        if is_member or request.couch_user.is_superuser:
            doc_info = doc_info_fn(doc)
        else:
            raise Http404()
        if redirect and doc_info.link:
            messages.info(request, _("We've redirected you to the %s matching your query") % doc_info.type_display)
            return HttpResponseRedirect(doc_info.link)
        elif redirect and request.couch_user.is_superuser:
            return HttpResponseRedirect('{}?id={}'.format(reverse('raw_doc'), doc.get('_id')))
        else:
            return json_response(doc_info)

    couch_dbs = [None] + settings.COUCH_SETTINGS_HELPER.extra_db_names
    for db_name in couch_dbs:
        try:
            doc = get_db(db_name).get(query)
        except ResourceNotFound:
            pass
        else:
            domain = doc.get('domain') or doc.get('domains', [None])[0]
            doc_info_fn = functools.partial(get_doc_info, domain_hint=domain)
            return deal_with_doc(doc, domain, doc_info_fn)

    for accessor in (FormAccessorSQL.get_form, CaseAccessorSQL.get_case):
        try:
            doc = accessor(query)
        except (XFormNotFound, CaseNotFound):
            pass
        else:
            domain = doc.domain
            return deal_with_doc(doc, domain, get_object_info)

    for django_model in (SQLLocation,):
        try:
            if hasattr(django_model, 'by_id') and callable(django_model.by_id):
                doc = django_model.by_id(query)
            else:
                doc = django_model.objects.get(pk=query)
        except django_model.DoesNotExist:
            continue
        else:
            if doc is None:
                continue
            domain = doc.domain
            return deal_with_doc(doc, domain, get_object_info)

    raise Http404()


def osdd(request, template='osdd.xml'):
    response = render(request, template, {
        'url_base': get_url_base(),
        'env': get_environment_friendly_name()
    })
    response['Content-Type'] = 'application/xml'
    return response


class MaintenanceAlertsView(BasePageView):
    urlname = 'alerts'
    page_title = ugettext_noop("Maintenance Alerts")
    template_name = 'hqwebapp/maintenance_alerts.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(MaintenanceAlertsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        from corehq.apps.hqwebapp.models import MaintenanceAlert
        return {
            'alerts': [{
                'created': str(alert.created),
                'active': alert.active,
                'html': alert.html,
                'id': alert.id,
                'domains': ", ".join(alert.domains) if alert.domains else "All domains",
            } for alert in MaintenanceAlert.objects.order_by('-active', '-created')[:20]]
        }

    @property
    def page_url(self):
        return reverse(self.urlname)


@require_POST
@require_superuser
def create_alert(request):
    from corehq.apps.hqwebapp.models import MaintenanceAlert
    alert_text = request.POST.get('alert_text')
    domains = request.POST.get('domains').split() or None
    MaintenanceAlert(active=False, text=alert_text, domains=domains).save()
    return HttpResponseRedirect(reverse('alerts'))


@require_POST
@require_superuser
def activate_alert(request):
    from corehq.apps.hqwebapp.models import MaintenanceAlert
    ma = MaintenanceAlert.objects.get(id=request.POST.get('alert_id'))
    ma.active = True
    ma.save()
    return HttpResponseRedirect(reverse('alerts'))


@require_POST
@require_superuser
def deactivate_alert(request):
    from corehq.apps.hqwebapp.models import MaintenanceAlert
    ma = MaintenanceAlert.objects.get(id=request.POST.get('alert_id'))
    ma.active = False
    ma.save()
    return HttpResponseRedirect(reverse('alerts'))


def redirect_to_dimagi(endpoint):
    def _redirect(request, lang_code=None):
        if settings.SERVER_ENVIRONMENT in [
            'production',
            'india',
            'staging',
            'changeme',
            settings.LOCAL_SERVER_ENVIRONMENT,
        ]:
            return HttpResponsePermanentRedirect(
                "https://www.dimagi.com/{}{}".format(
                    endpoint,
                    "?lang={}".format(lang_code) if lang_code else "",
                )
            )
        return redirect_to_default(request)
    return _redirect


def temporary_google_verify(request):
    # will remove once google search console verify process completes
    # BMB 4/20/18
    return render(request, "google9633af922b8b0064.html")


@waf_allow('XSS_BODY')
@require_POST
@csrf_exempt
def log_email_event(request, secret):
    # From Amazon SNS:
    # https://docs.aws.amazon.com/ses/latest/DeveloperGuide/event-publishing-retrieving-sns-examples.html

    if secret != settings.SNS_EMAIL_EVENT_SECRET:
        return HttpResponse("Incorrect secret", status=403, content_type='text/plain')

    request_json = json.loads(request.body)

    if request_json['Type'] == "SubscriptionConfirmation":
        # When creating an SNS topic, the first message is a subscription
        # confirmation, where we need to access the subscribe URL to confirm we
        # are able to receive messages at this endpoint
        subscribe_url = request_json['SubscribeURL']
        requests.get(subscribe_url)
        return HttpResponse()

    message = json.loads(request_json['Message'])
    headers = message.get('mail', {}).get('headers', [])

    for header in headers:
        if header["name"] == COMMCARE_MESSAGE_ID_HEADER:
            subevent_id = header["value"]
            break
    else:
        return HttpResponse()

    try:
        subevent = MessagingSubEvent.objects.get(id=subevent_id)
    except MessagingSubEvent.DoesNotExist:
        return HttpResponse()

    event_type = message.get('eventType')
    if event_type == 'Bounce':
        additional_error_text = ''

        bounce_type = message.get('bounce', {}).get('bounceType')
        if bounce_type:
            additional_error_text = f"{bounce_type}."
        bounced_recipients = message.get('bounce', {}).get('bouncedRecipients', [])
        recipient_addresses = []
        for bounced_recipient in bounced_recipients:
            recipient_addresses.append(bounced_recipient.get('emailAddress'))
        if recipient_addresses:
            additional_error_text = f"{additional_error_text} - {', '.join(recipient_addresses)}"

        subevent.error(MessagingEvent.ERROR_EMAIL_BOUNCED, additional_error_text=additional_error_text)
    elif event_type == 'Send':
        subevent.status = MessagingEvent.STATUS_EMAIL_SENT
    elif event_type == 'Delivery':
        subevent.status = MessagingEvent.STATUS_EMAIL_DELIVERED
        subevent.additional_error_text = message.get('delivery', {}).get('timestamp')

    subevent.save()

    return HttpResponse()
