from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import functools
import json
import logging
import os
import re
import sys
import traceback
import uuid
from datetime import datetime

from django.utils import html
from six.moves.urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import logout as django_logout
from django.core import cache
from django.core.mail.message import EmailMessage
from django.http import HttpResponseRedirect, HttpResponse, Http404, \
    HttpResponseServerError, HttpResponseNotFound, HttpResponseBadRequest, \
    HttpResponseForbidden, HttpResponsePermanentRedirect
from django.shortcuts import redirect, render
from django.template import loader
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import resolve
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop, LANGUAGE_SESSION_KEY


from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView
from django.views.generic.base import View
from djangular.views.mixins import JSONResponseMixin

import httpagentparser
from couchdbkit import ResourceNotFound
from two_factor.views import LoginView
from two_factor.forms import AuthenticationTokenForm, BackupTokenForm

from corehq.apps.analytics import ab_tests
from corehq.apps.hqadmin.service_checks import CHECKS, run_checks
from corehq.apps.users.landing_pages import get_redirect_url, get_cloudcare_urlname
from corehq.apps.users.models import CouchUser

from corehq.form_processor.utils.general import should_use_sql_backend
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from dimagi.utils.couch.database import get_db
from memoized import memoized

from dimagi.utils.django.request import mutable_querydict
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.web import get_url_base, json_response, get_site_domain
from no_exceptions.exceptions import Http403
from soil import DownloadBase
from soil import views as soil_views

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.decorators import require_superuser, login_and_domain_required, two_factor_exempt, \
    track_domain_request
from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import normalize_domain_name, get_domain_from_url
from corehq.apps.dropbox.decorators import require_dropbox_session
from corehq.apps.dropbox.exceptions import DropboxUploadAlreadyInProgress, DropboxInvalidToken
from corehq.apps.dropbox.models import DropboxUploadHelper
from corehq.apps.dropbox.views import DROPBOX_ACCESS_TOKEN, DropboxAuthInitiate
from corehq.apps.hqadmin.management.commands.deploy_in_progress import DEPLOY_IN_PROGRESS_FLAG
from corehq.apps.hqwebapp.doc_info import get_doc_info, get_object_info
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.hqwebapp.forms import EmailAuthenticationForm, CloudCareAuthenticationForm
from corehq.apps.hqwebapp.utils import get_environment_friendly_name, update_session_language
from corehq.apps.locations.permissions import location_safe
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.util import format_username
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.util.context_processors import commcare_hq_names
from corehq.util.datadog.const import DATADOG_UNKNOWN
from corehq.util.datadog.metrics import JSERROR_COUNT
from corehq.util.datadog.utils import create_datadog_event, sanitize_url
from corehq.util.datadog.gauges import datadog_counter, datadog_gauge
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.view_utils import reverse
import six
from six.moves import range


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

    if six.PY3:
        exc_message = six.text_type(exc)
    else:
        exc_message = exc.message
        if isinstance(exc_message, bytes):
            exc_message = exc_message.decode('utf-8')

    return 'Traceback (most recent call last):\n{}{}: {}'.format(
        ''.join(traceback.format_tb(tb)),
        type.__name__,
        exc_message
    )


def server_error(request, template_name='500.html'):
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

    return HttpResponseServerError(t.render(
        context={
            'MEDIA_URL': settings.MEDIA_URL,
            'STATIC_URL': settings.STATIC_URL,
            'domain': domain,
            '500traceback': traceback_key,
        },
        request=request,
    ))


def not_found(request, template_name='404.html'):
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
            from corehq.apps.registration.views import track_domainless_new_user
            track_domainless_new_user(req)
            return redirect('registration_domain')
        elif 1 == len(domains):
            from corehq.apps.dashboard.views import dashboard_default
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
                        return dashboard_default(req, domain)
                else:
                    if role and role.default_landing_page:
                        url = get_redirect_url(role.default_landing_page, domain)
                    elif couch_user.is_commcare_user():
                        url = reverse(get_cloudcare_urlname(domain), args=[domain])
                    else:
                        return dashboard_default(req, domain)
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
        tags = [
            'status:{}'.format('failed' if not status.success else 'ok'),
            'check:{}'.format(check_name)
        ]
        datadog_gauge('commcare.serverup.check', status.duration, tags=tags)

    if failed_checks and not is_deploy_in_progress():
        status_messages = [
            html.linebreaks('<strong>{}</strong>: {}'.format(check, html.escape(status.msg)).strip())
            for check, status in failed_checks
        ]
        create_datadog_event(
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


def no_permissions(request, redirect_to=None, template_name="403.html", message=None):
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
def _login(req, domain_name):

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
    template_name = 'login_and_password/login.html'
    custom_landing_page = settings.CUSTOM_LANDING_TEMPLATE
    if custom_landing_page:
        if isinstance(custom_landing_page, six.string_types):
            soft_assert_type_text(custom_landing_page)
            template_name = custom_landing_page
        else:
            template_name = custom_landing_page.get(req.get_host())
            if template_name is None:
                template_name = custom_landing_page.get('default', template_name)
    elif domain_name:
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
    return _login(req, domain)


@location_safe
def domain_login(req, domain):
    # This is a wrapper around the _login view which sets a different template
    project = Domain.get_by_name(domain)
    if not project:
        raise Http404

    # FYI, the domain context_processor will pick this up and apply the
    # necessary domain contexts:
    req.project = project

    return _login(req, domain)


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
def logout(req):
    referer = req.META.get('HTTP_REFERER')
    domain = get_domain_from_url(urlparse(referer).path) if referer else None

    # we don't actually do anything with the response here:
    django_logout(req, **{"template_name": settings.BASE_TEMPLATE})

    if referer and domain:
        domain_login_url = reverse('domain_login', kwargs={'domain': domain})
        return HttpResponseRedirect('%s' % domain_login_url)
    else:
        return HttpResponseRedirect(reverse('login'))


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


@require_POST
def jserror(request):
    agent = request.META.get('HTTP_USER_AGENT', None)
    os = browser_name = browser_version = bot = DATADOG_UNKNOWN
    if agent:
        parsed_agent = httpagentparser.detect(agent)
        bot = parsed_agent.get('bot', False)
        if 'os' in parsed_agent:
            os = parsed_agent['os'].get('name', DATADOG_UNKNOWN)

        if 'browser' in parsed_agent:
            browser_version = parsed_agent['browser'].get('version', DATADOG_UNKNOWN)
            browser_name = parsed_agent['browser'].get('name', DATADOG_UNKNOWN)

    datadog_counter(JSERROR_COUNT, tags=[
        'os:{}'.format(os),
        'browser_version:{}'.format(browser_version),
        'browser_name:{}'.format(browser_name),
        'url:{}'.format(sanitize_url(request.POST.get('page', None))),
        'file:{}'.format(request.POST.get('filename')),
        'bot:{}'.format(bot),
    ])

    return HttpResponse('')


@method_decorator([login_required], name='dispatch')
class BugReportView(View):

    @property
    def recipients(self):
        """
            Returns:
                list
        """
        return settings.BUG_REPORT_RECIPIENTS

    def post(self, req, *args, **kwargs):
        report = dict([(key, req.POST.get(key, '')) for key in (
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
            couch_user = req.couch_user
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

        message = (
            "username: {username}\n"
            "full name: {full_name}\n"
            "domain: {domain}\n"
            "url: {url}\n"
        ).format(**report)

        domain_object = Domain.get_by_name(domain) if report['domain'] else None
        debug_context = {
            'datetime': datetime.utcnow(),
            'self_started': '<unknown>',
            'scale_backend': '<unknown>',
            'has_handoff_info': '<unknown>',
            'project_description': '<unknown>',
            'sentry_error': '{}{}'.format(getattr(settings, 'SENTRY_QUERY_URL'), report['sentry_id'])
        }
        if domain_object:
            current_project_description = domain_object.project_description if domain_object else None
            new_project_description = req.POST.get('project_description')
            if (domain_object and
                    req.couch_user.is_domain_admin(domain=domain) and
                    new_project_description and current_project_description != new_project_description):
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
        cc = [el for el in report['cc'].strip().split(",") if el]

        if full_name and not any([c in full_name for c in '<>"']):
            reply_to = '"{full_name}" <{email}>'.format(**report)
        else:
            reply_to = report['email']

        # if the person looks like a commcare user, fogbugz can't reply
        # to their email, so just use the default
        if settings.HQ_ACCOUNT_ROOT in reply_to:
            reply_to = settings.SERVER_EMAIL

        message += "Message:\n\n{message}\n".format(message=report['message'])
        if req.POST.get('five-hundred-report'):
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
            to=self.recipients,
            headers={'Reply-To': reply_to},
            cc=cc
        )

        uploaded_file = req.FILES.get('report_issue')
        if uploaded_file:
            filename = uploaded_file.name
            content = uploaded_file.read()
            email.attach(filename=filename, content=content)

        # only fake the from email if it's an @dimagi.com account
        is_icds_env = settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS
        if re.search(r'@dimagi\.com$', report['username']) and not is_icds_env:
            email.from_email = report['username']
        else:
            email.from_email = settings.CCHQ_BUG_REPORT_EMAIL

        email.send(fail_silently=False)

        if req.POST.get('five-hundred-report'):
            messages.success(
                req,
                "Your CommCare HQ Issue Report has been sent. We are working quickly to resolve this problem."
            )
            return HttpResponseRedirect(reverse('homepage'))

        return HttpResponse()


def render_static(request, template, page_name):
    """
    Takes an html file and renders it Commcare HQ's styling
    """
    return render(request, "hqwebapp/blank.html",
                  {'tmpl': template, 'page_name': page_name})


def cda(request):
    return render_static(request, "cda.html", _("Content Distribution Agreement"))


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
        raise NotImplementedError("you need to implement get_param_source")

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
        if request.couch_user.is_superuser or (domain and request.couch_user.is_member_of(domain)):
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
                'created': six.text_type(alert.created),
                'active': alert.active,
                'html': alert.html,
                'id': alert.id,
                'domains': ", ".join(alert.domains) if alert.domains else "All domains",
            } for alert in MaintenanceAlert.objects.order_by('-active', '-created')[:5]]
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
            'localdev',
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
