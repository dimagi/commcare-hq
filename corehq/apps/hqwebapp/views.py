import json
import logging
import os
import pytz
import re
import sys
import traceback
import uuid
from datetime import datetime
from urllib.parse import urlparse
from oauth2_provider.models import get_application_model

import httpagentparser
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView
from django.core import cache
from django.core.mail.message import EmailMessage
from django.forms import modelform_factory
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
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop, activate
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView
from django.views.generic.base import View
from memoized import memoized
from sentry_sdk import last_event_id
from two_factor.utils import default_device
from two_factor.views import LoginView

from corehq.apps.accounting.decorators import (
    always_allow_project_access,
)
from corehq.apps.accounting.models import Subscription
from corehq.apps.analytics import ab_tests
from corehq.apps.app_manager.dbaccessors import get_app_cached, get_latest_released_build_id
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
from corehq.apps.email.models import EmailSettings
from corehq.apps.hqadmin.management.commands.deploy_in_progress import (
    DEPLOY_IN_PROGRESS_FLAG,
)
from corehq.apps.hqadmin.service_checks import CHECKS, run_checks
from corehq.apps.hqwebapp.decorators import waf_allow, use_bootstrap5
from corehq.apps.hqwebapp.doc_info import get_doc_info
from corehq.apps.hqwebapp.doc_lookup import lookup_doc_id
from corehq.apps.hqwebapp.encoders import LazyEncoder
from corehq.apps.hqwebapp.forms import (
    CloudCareAuthenticationForm,
    EmailAuthenticationForm,
    HQAuthenticationTokenForm,
    HQBackupTokenForm
)
from corehq.apps.hqwebapp.models import HQOauthApplication
from corehq.apps.hqwebapp.login_utils import get_custom_login_page
from corehq.apps.hqwebapp.utils import get_environment_friendly_name
from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version
from corehq.apps.locations.permissions import location_safe
from corehq.apps.sms.event_handlers import handle_email_messaging_subevent
from corehq.apps.users.event_handlers import handle_email_invite_message
from corehq.apps.users.landing_pages import get_redirect_url
from corehq.apps.users.models import CouchUser, Invitation
from corehq.apps.users.util import format_username, is_dimagi_email
from corehq.toggles import CLOUDCARE_LATEST_BUILD
from corehq.util.context_processors import commcare_hq_names
from corehq.util.email_event_utils import handle_email_sns_event
from corehq.util.metrics import create_metrics_event, metrics_counter, metrics_gauge
from corehq.util.metrics.const import TAG_UNKNOWN, MPM_MAX
from corehq.util.metrics.utils import sanitize_url
from corehq.util.public_only_requests.public_only_requests import get_public_only_session
from corehq.util.timezones.conversions import ServerTime, UserTime
from corehq.util.view_utils import reverse
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.request_helpers import is_request_using_sso
from corehq.apps.sso.utils.domain_helpers import is_domain_using_sso
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache
from dimagi.utils.django.email import COMMCARE_MESSAGE_ID_HEADER
from dimagi.utils.django.request import mutable_querydict
from dimagi.utils.logging import notify_exception, notify_error
from dimagi.utils.web import get_url_base
from no_exceptions.exceptions import Http403
from soil import DownloadBase
from soil import views as soil_views


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


@use_bootstrap5
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
    cache.cache.set(traceback_key, traceback_text, 60 * 60)

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


@use_bootstrap5
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
        if domain is not None:
            url = reverse('domain_login', args=[domain])
        else:
            url = reverse('login')
        return HttpResponseRedirect(url)

    if domain and _two_factor_needed(domain, req):
        return TemplateResponse(
            request=req,
            template='two_factor/core/otp_required.html',
            status=403,
        )

    if domain:
        domain = normalize_domain_name(domain)
        domains = [Domain.get_by_name(domain)]
    else:
        domains = Domain.active_for_user(req.user)

    if not domains:
        return redirect('registration_domain')

    if len(domains) > 1:
        return HttpResponseRedirect(settings.DOMAIN_SELECT_URL)

    from corehq.apps.users.models import DomainMembershipError

    domain = domains[0]
    if not domain:
        raise Http404()

    domain_name = domain.name
    couch_user = req.couch_user
    try:
        role = couch_user.get_role(domain_name)
    except DomainMembershipError:
        # commcare users without roles should always be denied access
        if couch_user.is_commcare_user():
            raise Http404()
        else:
            # web users without roles are redirected to the dashboard default
            # view since some domains allow web users to request access if they
            # don't have it
            url = reverse("dashboard_domain", args=[domain_name])
    else:
        url = None
        if role and role.default_landing_page:
            try:
                url = get_redirect_url(role.default_landing_page, domain_name)
            except ValueError:
                pass  # landing page no longer accessible to domain

        if url is None:
            if couch_user.is_commcare_user():
                url = reverse('formplayer_main', args=[domain_name])
            else:
                url = reverse("dashboard_domain", args=[domain_name])

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


@use_bootstrap5
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


@use_bootstrap5
def no_permissions(request, redirect_to=None, template_name="403.html", message=None, exception=None):
    """
    403 error handler.
    """
    return HttpResponseForbidden(_no_permissions_message(request, template_name, message))


@use_bootstrap5
def no_permissions_exception(request, template_name="403.html", message=None):
    return Http403(_no_permissions_message(request, template_name, message))


@use_bootstrap5
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

    if 'auth-username' in req.POST:
        couch_user = CouchUser.get_by_username(req.POST['auth-username'].lower())
        if couch_user:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, couch_user.language)
            # reset cookie to an empty list on login to show domain alerts again
            response.set_cookie('viewed_domain_alerts', [])
            activate(couch_user.language)

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


@xframe_options_sameorigin
@location_safe
def iframe_domain_login(req, domain):
    return domain_login(req, domain, custom_template_name="hqwebapp/iframe_domain_login.html", extra_context={
        'current_page': {'page_name': _('Your session has expired')},
        'restrict_domain_creation': True,
        'is_session_expiration': True,
        'ANALYTICS_IDS': {},
    })


@xframe_options_sameorigin
@location_safe
def iframe_sso_login_pending(request):
    return TemplateView.as_view(template_name='hqwebapp/bootstrap3/iframe_sso_login_pending.html')(request)


class HQLoginView(LoginView):
    form_list = [
        (LoginView.AUTH_STEP, EmailAuthenticationForm),
        (LoginView.TOKEN_STEP, HQAuthenticationTokenForm),
        (LoginView.BACKUP_STEP, HQBackupTokenForm),
    ]
    extra_context = {}

    def has_token_step(self):
        """
        Overrides the two_factor LoginView has_token_step to ensure this step is excluded if a valid backup
        token exists. Created https://github.com/jazzband/django-two-factor-auth/issues/709 to track work to
        potentially include this in django-two-factor-auth directly.
        """
        return (
            default_device(self.get_user())
            and self.BACKUP_STEP not in self.storage.validated_step_data
            and not self.remember_agent
        )

    # override two_factor LoginView condition_dict to include the method defined above
    condition_dict = {
        LoginView.TOKEN_STEP: has_token_step,
        LoginView.BACKUP_STEP: LoginView.has_backup_step,
    }

    def post(self, *args, **kwargs):
        if settings.ENFORCE_SSO_LOGIN and self.steps.current == self.AUTH_STEP:
            # catch anyone who by-passes the javascript and tries to log in directly
            username = self.request.POST.get('auth-username')
            idp = IdentityProvider.get_required_identity_provider(username) if username else None
            if idp:
                return HttpResponseRedirect(idp.get_login_url(username=username))
        return super().post(*args, **kwargs)

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        # The forms need the request to properly log authentication failures
        kwargs.setdefault('request', self.request)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(HQLoginView, self).get_context_data(**kwargs)
        context.update(self.extra_context)
        context['enforce_sso_login'] = (
            settings.ENFORCE_SSO_LOGIN
            and self.steps.current == self.AUTH_STEP
        )
        domain = context.get('domain')
        if domain and not is_domain_using_sso(domain):
            # ensure that domain login pages not associated with SSO do not
            # enforce SSO on the login screen
            context['enforce_sso_login'] = False
        return context


class CloudCareLoginView(HQLoginView):
    form_list = [
        (HQLoginView.AUTH_STEP, CloudCareAuthenticationForm),
        (HQLoginView.TOKEN_STEP, HQAuthenticationTokenForm),
        (HQLoginView.BACKUP_STEP, HQBackupTokenForm),
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
    current_build_id = request.GET.get('selected_app_id', '')
    domain = request.GET.get('domain', '')
    new_app_version_available = False
    # Do not show popup to users who have use_latest_build_cloudcare ff enabled
    latest_build_ff_enabled = (CLOUDCARE_LATEST_BUILD.enabled(domain)
                or CLOUDCARE_LATEST_BUILD.enabled(request.user.username))
    if current_build_id and domain and not latest_build_ff_enabled:
        app = get_app_cached(domain, current_build_id)
        app_id = app['copy_of'] if app['copy_of'] else app['_id']
        latest_build_id = get_latest_released_build_id(domain, app_id)

        if latest_build_id:
            new_app_version_available = current_build_id != latest_build_id

    return JsonResponse({
        'success': request.user.is_authenticated,
        'session_expiry': request.session.get('session_expiry'),
        'secure_session': request.session.get('secure_session'),
        'secure_session_timeout': request.session.get('secure_session_timeout'),
        'username': request.user.username,
        'new_app_version_available': new_app_version_available,
    })


@location_safe
@login_required
def login_new_window(request):
    return render_static(request, "hqwebapp/close_window.html", _("Thank you for logging in!"))


@xframe_options_sameorigin
@location_safe
@login_required
def domain_login_new_window(request):
    template = ('hqwebapp/bootstrap3/iframe_sso_login_success.html'
                if is_request_using_sso(request)
                else 'hqwebapp/bootstrap3/iframe_close_window.html')
    return TemplateView.as_view(template_name=template)(request)


@login_and_domain_required
@track_domain_request(calculated_prop='cp_n_downloads_custom_exports')
def retrieve_download(req, domain, download_id, template="hqwebapp/includes/bootstrap3/file_download.html"):
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

    if download.owner_ids and request.couch_user.get_id not in download.owner_ids:
        return no_permissions(request, message=_(
            "You do not have access to this file. It can only be uploaded to dropbox by the user who created it"
        ))

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
        notify_exception(
            request,
            "If you want to achieve a 500-style email-out but don't want the user to see a 500, "
            "use notify_exception(request[, message])")
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


def _get_email_message_base(post_params, couch_user, uploaded_file, to_email):
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
        to=[to_email],
        headers={'Reply-To': reply_to},
        cc=other_recipients
    )

    if uploaded_file:
        filename = uploaded_file.name
        content = uploaded_file.read()
        email.attach(filename=filename, content=content)

    # only fake the from email if it's an @dimagi.com account
    is_icds_env = settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS
    if is_dimagi_email(report['username']) and not is_icds_env:
        email.from_email = report['username']
    else:
        email.from_email = to_email

    return email


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
        return _get_email_message_base(
            post_params,
            couch_user,
            uploaded_file,
            to_email=settings.SUPPORT_EMAIL,
        )


@method_decorator([login_required], name='dispatch')
class SolutionsFeatureRequestView(View):
    urlname = 'solutions_feature_request'

    @property
    def to_email_address(self):
        return 'solutions-feedback@dimagi.com'

    def post(self, request, *args, **kwargs):
        if not settings.IS_DIMAGI_ENVIRONMENT or not request.couch_user.is_dimagi:
            return HttpResponse(status=400)
        email = _get_email_message_base(
            post_params=request.POST,
            couch_user=request.couch_user,
            uploaded_file=request.FILES.get('feature_request'),
            to_email=self.to_email_address,
        )
        email.send(fail_silently=False)
        return HttpResponse()


def render_static(request, template, page_name):
    """
    Takes an html file and renders it Commcare HQ's styling
    """
    return render(request, f"hqwebapp/{get_bootstrap_version()}/blank.html",
                  {'tmpl': template, 'page_name': page_name})


@use_bootstrap5
def apache_license(request):
    return render_static(request, "apache_license.html", _("Apache License"))


@use_bootstrap5
def bsd_license(request):
    return render_static(request, "bsd_license.html", _("BSD License"))


class BasePageView(TemplateView):
    urlname = None  # name of the view used in urls
    page_title = None  # what shows up in the <title>
    template_name = 'hqwebapp/bootstrap3/base_page.html'

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
    template_name = "hqwebapp/bootstrap3/base_section.html"

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

    limit_text = gettext_noop("items per page")
    empty_notification = gettext_noop("You have no items.")
    loading_message = gettext_noop("Loading...")
    deleted_items_header = gettext_noop("Deleted Items:")
    new_items_header = gettext_noop("New Items:")

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
                'create_item_form': (
                    html.escape(self.get_create_form_response(create_form)) if create_form else None),
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

    result = lookup_doc_id(query)
    if not result:
        raise Http404()

    is_member = result.domain and request.couch_user.is_member_of(result.domain, allow_enterprise=True)
    if is_member or request.couch_user.is_superuser:
        doc_info = get_doc_info(result.doc)
        if (doc_info.type == 'CommCareCase' or doc_info.type == 'XFormInstance') and doc_info.is_deleted:
            raise Http404()
    else:
        raise Http404()
    if redirect and doc_info.link:
        messages.info(request, _("We've redirected you to the %s matching your query") % doc_info.type_display)
        return HttpResponseRedirect(doc_info.link)
    elif redirect and request.couch_user.is_superuser:
        return HttpResponseRedirect('{}?id={}'.format(reverse('raw_doc'), result.doc_id))
    else:
        return JsonResponse(doc_info.to_json())


def osdd(request, template='osdd.xml'):
    response = render(request, template, {
        'url_base': get_url_base(),
        'env': get_environment_friendly_name()
    })
    response['Content-Type'] = 'application/xml'
    return response


class MaintenanceAlertsView(BasePageView):
    urlname = 'alerts'
    page_title = gettext_noop("Maintenance Alerts")
    template_name = 'hqwebapp/maintenance_alerts.html'

    @method_decorator(use_bootstrap5)
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(MaintenanceAlertsView, self).dispatch(request, *args, **kwargs)

    @method_decorator(require_superuser)
    def post(self, request):
        from corehq.apps.hqwebapp.models import Alert
        ma = Alert.objects.get(id=request.POST.get('alert_id'), created_by_domain=None)
        command = request.POST.get('command')
        if command == 'activate':
            ma.active = True
        elif command == 'deactivate':
            ma.active = False
        ma.save()
        return HttpResponseRedirect(reverse('alerts'))

    @property
    def page_context(self):
        from corehq.apps.hqwebapp.models import Alert
        now = datetime.utcnow()
        alerts = Alert.objects.filter(
            created_by_domain__isnull=True
        ).order_by('-active', '-created')[:20]
        return {
            'timezones': pytz.common_timezones,
            'alerts': [{
                'created': str(alert.created),
                'active': alert.active,
                'html': alert.html,
                'start_time': ServerTime(alert.start_time).user_time(pytz.timezone(alert.timezone))
                                                          .ui_string() if alert.start_time else None,
                'end_time': ServerTime(alert.end_time).user_time(pytz.timezone(alert.timezone))
                                                      .ui_string() if alert.end_time else None,
                'expired': alert.end_time and alert.end_time < now,
                'id': alert.id,
                'domains': ", ".join(alert.domains) if alert.domains else "All domains",
                'created_by_user': alert.created_by_user,
            } for alert in alerts]
        }

    @property
    def page_url(self):
        return reverse(self.urlname)


@require_POST
@require_superuser
def create_alert(request):
    from corehq.apps.hqwebapp.models import Alert
    alert_text = request.POST.get('alert_text')
    domains = request.POST.get('domains')
    domains = domains.split() if domains else None

    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    timezone = request.POST.get('timezone') or 'UTC'

    start_time = UserTime(
        datetime.fromisoformat(start_time),
        tzinfo=pytz.timezone(timezone)
    ).server_time().done() if start_time else None
    end_time = UserTime(
        datetime.fromisoformat(end_time),
        tzinfo=pytz.timezone(timezone)
    ).server_time().done() if end_time else None

    Alert(active=False, text=alert_text, domains=domains,
          start_time=start_time, end_time=end_time, timezone=timezone,
          created_by_user=request.couch_user.username).save()
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
def log_email_event(request, secret, domain=None):
    # From Amazon SNS:
    # https://docs.aws.amazon.com/ses/latest/DeveloperGuide/event-publishing-retrieving-sns-examples.html
    email_setting = EmailSettings.objects.filter(domain=domain).first() if domain else None
    if (email_setting and email_setting.use_this_gateway and email_setting.use_tracking_headers):
        SNS_email_event_secret = email_setting.sns_secret
    else:
        SNS_email_event_secret = settings.SNS_EMAIL_EVENT_SECRET
    if secret != SNS_email_event_secret:
        return HttpResponse("Incorrect secret", status=403, content_type='text/plain')

    request_json = json.loads(request.body)

    if request_json['Type'] == "SubscriptionConfirmation":
        # When creating an SNS topic, the first message is a subscription
        # confirmation, where we need to access the subscribe URL to confirm we
        # are able to receive messages at this endpoint
        subscribe_url = request_json['SubscribeURL']
        session = get_public_only_session(domain_name='n/a', src="log_email_event")
        session.get(subscribe_url)
        return HttpResponse()

    message = json.loads(request_json['Message'])
    headers = message.get('mail', {}).get('headers', [])

    for header in headers:
        if header["name"] == COMMCARE_MESSAGE_ID_HEADER:
            if Invitation.EMAIL_ID_PREFIX in header["value"]:
                handle_email_invite_message(message, header["value"].split(Invitation.EMAIL_ID_PREFIX)[1])
            else:
                subevent_id = header["value"]
                handle_email_messaging_subevent(message, subevent_id)
            break

    handle_email_sns_event(message)

    return HttpResponse()


@method_decorator(require_superuser, name="dispatch")
class OauthApplicationRegistration(BasePageView):
    urlname = 'oauth_application_registration'
    page_title = "Oauth Application Registration"
    template_name = "hqwebapp/bootstrap3/oauth_application_registration_form.html"

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def base_application_form(self):
        return modelform_factory(
            get_application_model(),
            fields=(
                "name",
                "client_id",
                "client_secret",
                "client_type",
                "authorization_grant_type",
                "redirect_uris",
            ),
        )

    @property
    def hq_application_form(self):
        return modelform_factory(
            HQOauthApplication,
            fields=(
                "pkce_required",
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'forms' not in kwargs:
            context['forms'] = [self.base_application_form(), self.hq_application_form()]
        return context

    def post(self, request, *args, **kwargs):

        base_application_form = self.base_application_form(data=self.request.POST)
        hq_application_form = self.hq_application_form(data=self.request.POST)

        if base_application_form.is_valid() and hq_application_form.is_valid():
            base_application_form.instance.user = self.request.user
            base_application = base_application_form.save()
            HQOauthApplication.objects.create(
                application=base_application,
                **hq_application_form.cleaned_data,
            )
        else:
            return self.render_to_response(self.get_context_data(
                forms=[base_application_form, hq_application_form]
            ))

        return HttpResponseRedirect(reverse('oauth2_provider:detail', args=[str(base_application.id)]))


@csrf_exempt
@require_POST
def check_sso_login_status(request):
    """
    Checks to see if a given username must sign in or sign up with SSO and
    returns the url for the SSO's login endpoint.
    :param request: HttpRequest
    :return: HttpResponse (as JSON)
    """
    username = request.POST['username']
    is_sso_required = False
    sso_url = None
    continue_text = None

    idp = IdentityProvider.get_required_identity_provider(username)
    if idp:
        is_sso_required = True
        sso_url = idp.get_login_url(username=username)
        continue_text = _("Continue to {}").format(idp.name)

    return JsonResponse({
        'is_sso_required': is_sso_required,
        'sso_url': sso_url,
        'continue_text': continue_text,
    })
