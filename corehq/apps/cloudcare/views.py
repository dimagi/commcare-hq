import json
import re
import string

import requests
import sentry_sdk
from django.conf import settings
from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import redirect, render

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.decorators.clickjacking import xframe_options_sameorigin

import urllib.parse
from text_unidecode import unidecode

from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.formplayer_api.utils import get_formplayer_url
from corehq.util.metrics import metrics_counter
from couchforms.const import VALID_ATTACHMENT_FILE_EXTENSION_MAP
from dimagi.utils.logging import notify_error, notify_exception
from dimagi.utils.web import json_response

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import (
    requires_privilege_for_commcare_user,
    requires_privilege_with_fallback,
)
from corehq.apps.accounting.utils import domain_is_on_trial, domain_has_privilege
from corehq.apps.domain.models import Domain

from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_app_ids_in_domain,
    get_current_app,
    get_current_app_doc,
    get_latest_build_doc,
    get_latest_build_id,
    get_latest_released_app_doc,
    get_latest_released_build_id,
)

from corehq.apps.cloudcare.const import (
    PREVIEW_APP_ENVIRONMENT,
    WEB_APPS_ENVIRONMENT,
)
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps, get_application_access_for_domain
from corehq.apps.cloudcare.decorators import require_cloudcare_access
from corehq.apps.cloudcare.esaccessors import login_as_user_query
from corehq.apps.cloudcare.models import SQLAppGroup
from corehq.apps.cloudcare.utils import get_mobile_ucr_count, should_restrict_web_apps_usage
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
    login_or_digest_ex,
)
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.decorators import (
    use_bootstrap5,
    use_daterangepicker,
    use_jquery_ui,
    waf_allow,
)
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import can_use_restore_as
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.formdetails import readable
from corehq.apps.users.decorators import require_can_login_as
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.apps.users.views import BaseUserSettingsView
from corehq.apps.integration.util import integration_contexts
from corehq.util.metrics import metrics_histogram
from xml2json.lib import xml2json

from langcodes import get_name


@require_cloudcare_access
def default(request, domain):
    return HttpResponseRedirect(reverse('formplayer_main', args=[domain]))


@location_safe
class FormplayerMain(View):

    preview = False
    urlname = 'formplayer_main'

    @xframe_options_sameorigin
    @use_daterangepicker
    @use_jquery_ui
    @method_decorator(require_cloudcare_access)
    @method_decorator(requires_privilege_for_commcare_user(privileges.CLOUDCARE))
    def dispatch(self, request, *args, **kwargs):
        return super(FormplayerMain, self).dispatch(request, *args, **kwargs)

    def fetch_app(self, domain, app_id):
        return _fetch_build(domain, self.request.couch_user.username, app_id)

    def get_web_apps_available_to_user(self, domain, user):
        app_access = get_application_access_for_domain(domain)
        app_ids = get_app_ids_in_domain(domain)

        apps = list(map(
            lambda app_id: self.fetch_app(domain, app_id),
            app_ids,
        ))
        apps = filter(None, apps)
        apps = filter(lambda app: app.get('cloudcare_enabled') or self.preview, apps)
        apps = filter(lambda app: app_access.user_can_access_app(user, app), apps)
        apps = [_format_app_doc(app) for app in apps]
        apps = sorted(apps, key=lambda app: app['name'].lower())
        return apps

    @staticmethod
    def get_restore_as_user(request, domain):
        """
        returns (user, set_cookie), where set_cookie is a function to be called on
        the eventual response
        """

        if not hasattr(request, 'couch_user'):
            raise Http404()

        def set_cookie(response):  # set_coookie is a noop by default
            return response

        cookie_name = urllib.parse.quote(
            'restoreAs:{}:{}'.format(domain, request.couch_user.username))
        username = request.COOKIES.get(cookie_name)
        if username:
            user = CouchUser.get_by_username(format_username(username, domain))
            if user:
                return user, set_cookie
            else:
                def set_cookie(response):  # overwrite the default noop set_cookie
                    response.delete_cookie(cookie_name)
                    return response

        elif request.couch_user.has_permission(domain, 'limited_login_as'):
            login_as_users = login_as_user_query(
                domain,
                request.couch_user,
                search_string='',
                limit=1,
                offset=0
            ).run()
            if login_as_users.total == 1:
                def set_cookie(response):
                    response.set_cookie(cookie_name, user.raw_username)
                    return response

                user = CouchUser.get_by_username(login_as_users.hits[0]['username'])
                return user, set_cookie

        return request.couch_user, set_cookie

    def get(self, request, domain):
        mobile_ucr_count = get_mobile_ucr_count(domain)
        if should_restrict_web_apps_usage(domain, mobile_ucr_count):
            return redirect('block_web_apps', domain=domain)

        option = request.GET.get('option')
        if option == 'apps':
            return self.get_option_apps(request, domain)
        else:
            return self.get_main(request, domain)

    def get_option_apps(self, request, domain):
        restore_as, set_cookie = self.get_restore_as_user(request, domain)
        apps = self.get_web_apps_available_to_user(domain, restore_as)
        return JsonResponse(apps, safe=False)

    def get_main(self, request, domain):
        restore_as, set_cookie = self.get_restore_as_user(request, domain)
        apps = self.get_web_apps_available_to_user(domain, restore_as)

        def _default_lang():
            try:
                return apps[0]['langs'][0]
            except Exception:
                return 'en'

        # default language to user's preference, followed by
        # first app's default, followed by english
        language = request.couch_user.language or _default_lang()

        domain_obj = Domain.get_by_name(domain)

        lang_codes = set().union(*(app.get("langs", []) for app in apps))
        lang_code_name_mapping = {code: get_name(code) for code in lang_codes}

        context = {
            "domain": domain,
            "default_geocoder_location": domain_obj.default_geocoder_location,
            "language": language,
            "apps": apps,
            "domain_is_on_trial": domain_is_on_trial(domain),
            "mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN,
            "username": request.couch_user.username,
            "formplayer_url": get_formplayer_url(for_js=True),
            "single_app_mode": False,
            "home_url": reverse(self.urlname, args=[domain]),
            "environment": WEB_APPS_ENVIRONMENT,
            "integrations": integration_contexts(domain),
            "has_geocoder_privs": has_geocoder_privs(domain),
            "valid_multimedia_extensions_map": VALID_ATTACHMENT_FILE_EXTENSION_MAP,
            "lang_code_name_mapping": lang_code_name_mapping,
        }

        return set_cookie(
            render(request, "cloudcare/formplayer_home.html", context)
        )


def _fetch_build(domain, username, app_id):
    if (toggles.CLOUDCARE_LATEST_BUILD.enabled(domain) or toggles.CLOUDCARE_LATEST_BUILD.enabled(username)):
        return get_latest_build_doc(domain, app_id)
    else:
        return get_latest_released_app_doc(domain, app_id)


def _fetch_build_id(domain, username, app_id):
    if (toggles.CLOUDCARE_LATEST_BUILD.enabled(domain) or toggles.CLOUDCARE_LATEST_BUILD.enabled(username)):
        return get_latest_build_id(domain, app_id)
    else:
        return get_latest_released_build_id(domain, app_id)


class FormplayerMainPreview(FormplayerMain):

    preview = True
    urlname = 'formplayer_main_preview'

    def fetch_app(self, domain, app_id):
        return get_current_app_doc(domain, app_id)


class FormplayerPreviewSingleApp(View):

    urlname = 'formplayer_single_app'

    @use_jquery_ui
    @method_decorator(require_cloudcare_access)
    @method_decorator(requires_privilege_for_commcare_user(privileges.CLOUDCARE))
    def dispatch(self, request, *args, **kwargs):
        return super(FormplayerPreviewSingleApp, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, app_id, **kwargs):
        app_access = get_application_access_for_domain(domain)

        app = get_current_app(domain, app_id)

        if not app_access.user_can_access_app(request.couch_user, app):
            raise Http404()

        def _default_lang():
            try:
                return app['langs'][0]
            except Exception:
                return 'en'

        # default language to user's preference, followed by
        # first app's default, followed by english
        language = request.couch_user.language or _default_lang()
        domain_obj = Domain.get_by_name(domain)

        context = {
            "domain": domain,
            "default_geocoder_location": domain_obj.default_geocoder_location,
            "language": language,
            "apps": [_format_app_doc(app)],
            "mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN,
            "username": request.user.username,
            "formplayer_url": get_formplayer_url(for_js=True),
            "single_app_mode": True,
            "home_url": reverse(self.urlname, args=[domain, app_id]),
            "environment": WEB_APPS_ENVIRONMENT,
            "integrations": integration_contexts(domain),
            "has_geocoder_privs": has_geocoder_privs(domain),
            "valid_multimedia_extensions_map": VALID_ATTACHMENT_FILE_EXTENSION_MAP,
        }
        return render(request, "cloudcare/formplayer_home.html", context)


class PreviewAppView(TemplateView):
    template_name = 'cloudcare/preview_app.html'
    urlname = 'preview_app'

    @use_daterangepicker
    @xframe_options_sameorigin
    def get(self, request, *args, **kwargs):
        mobile_ucr_count = get_mobile_ucr_count(request.domain)
        if should_restrict_web_apps_usage(request.domain, mobile_ucr_count):
            context = BlockWebAppsView.get_context_for_ucr_limit_error(request.domain, mobile_ucr_count)
            return render(request, 'cloudcare/block_preview_app.html', context)
        app = get_app(request.domain, kwargs.pop('app_id'))
        return self.render_to_response({
            'app': _format_app_doc(app.to_json()),
            'formplayer_url': get_formplayer_url(for_js=True),
            "mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN,
            "environment": PREVIEW_APP_ENVIRONMENT,
            "integrations": integration_contexts(request.domain),
            "has_geocoder_privs": has_geocoder_privs(request.domain),
            "valid_multimedia_extensions_map": VALID_ATTACHMENT_FILE_EXTENSION_MAP,
        })


def has_geocoder_privs(domain):
    return (
        toggles.USH_CASE_CLAIM_UPDATES.enabled(domain)
        and domain_has_privilege(domain, privileges.GEOCODER)
    )


@location_safe
class LoginAsUsers(View):

    http_method_names = ['get']
    urlname = 'login_as_users'

    @method_decorator(login_and_domain_required)
    @method_decorator(require_can_login_as)
    @method_decorator(requires_privilege_for_commcare_user(privileges.CLOUDCARE))
    def dispatch(self, *args, **kwargs):
        return super(LoginAsUsers, self).dispatch(*args, **kwargs)

    def get(self, request, domain, **kwargs):
        self.domain = domain
        self.couch_user = request.couch_user

        try:
            limit = int(request.GET.get('limit', 10))
        except ValueError:
            limit = 10

        # front end pages start at one
        try:
            page = int(request.GET.get('page', 1))
        except ValueError:
            page = 1
        query = request.GET.get('query')

        users_query = self._user_query(query, page - 1, limit)
        total_records = users_query.count()
        users_data = users_query.run()

        return json_response({
            'response': {
                'itemList': list(map(self._format_user, users_data.hits)),
                'total': users_data.total,
                'page': page,
                'query': query,
                'total_records': total_records
            },
        })

    def _user_query(self, search_string, page, limit):
        return login_as_user_query(
            self.domain,
            self.couch_user,
            search_string,
            limit,
            page * limit,
        )

    def _format_user(self, user_json):
        user = CouchUser.wrap_correctly(user_json)
        formatted_user = {
            'username': user.raw_username,
            'customFields': user.get_user_data(self.domain).to_dict(),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phoneNumbers': user.phone_numbers,
            'user_id': user.user_id,
            'location': user.sql_location.to_json() if user.sql_location else None,
        }
        return formatted_user


def _format_app_doc(doc):
    keys = ['_id', 'copy_of', 'langs', 'multimedia_map', 'name', 'profile', 'upstream_app_id']
    context = {key: doc.get(key) for key in keys}
    context['imageUri'] = doc.get('logo_refs', {}).get('hq_logo_web_apps', {}).get('path', '')
    return context


cloudcare_api = login_or_digest_ex(allow_cc_users=True)


class ReadableQuestions(View):

    urlname = 'readable_questions'

    @csrf_exempt
    @method_decorator(cloudcare_api)
    def dispatch(self, request, *args, **kwargs):
        return super(ReadableQuestions, self).dispatch(request, *args, **kwargs)

    def post(self, request, domain):
        instance_xml = request.POST.get('instanceXml').encode('utf-8')
        app_id = request.POST.get('appId')
        xmlns = request.POST.get('xmlns')

        _, form_data_json = xml2json(instance_xml)
        pretty_questions = readable.get_questions(domain, app_id, xmlns)

        readable_form = readable.get_readable_form_data(form_data_json, pretty_questions)

        rendered_readable_form = render_to_string(
            'reports/form/partials/readable_form.html',
            {'questions': readable_form}
        )

        return json_response({
            'form_data': rendered_readable_form,
            'form_questions': pretty_questions
        })


class HttpResponseConflict(HttpResponse):
    status_code = 409


class EditCloudcareUserPermissionsView(BaseUserSettingsView):
    template_name = 'cloudcare/config.html'
    urlname = 'cloudcare_app_settings'

    @property
    def page_title(self):
        return _("Web Apps Permissions")

    @use_bootstrap5
    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.CLOUDCARE))
    def dispatch(self, request, *args, **kwargs):
        return super(EditCloudcareUserPermissionsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        apps = get_cloudcare_apps(self.domain)
        access = get_application_access_for_domain(self.domain)
        groups = Group.by_domain(self.domain)
        return {
            'apps': apps,
            'groups': groups,
            'access': access.get_template_json(apps),
        }

    def put(self, request, *args, **kwargs):
        body = json.loads(request.body.decode('utf-8'))
        access = get_application_access_for_domain(self.domain)
        access.restrict = body['restrict']
        access.sqlappgroup_set.all().delete()
        access.sqlappgroup_set.set([
            SQLAppGroup(app_id=app_group['app_id'], group_id=app_group.get('group_id'))
            for app_group in body['app_groups']
        ], bulk=False)
        access.save()
        return json_response({'success': 1})


@waf_allow('XSS_BODY')
@location_safe
@login_and_domain_required
def report_formplayer_error(request, domain):
    data = json.loads(request.body)
    error_type = data.get('type')

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("cloudcare_error_type", error_type)

    if error_type == 'webformsession_request_failure':
        metrics_counter('commcare.formplayer.webformsession_request_failure', tags={
            'request': data.get('request'),
            'statusText': data.get('statusText'),
            'state': data.get('state'),
            'status': data.get('status'),
            'domain': domain,
            'cloudcare_env': data.get('cloudcareEnv'),
        })
        message = data.get("message") or "request failure in web form session"
        thread_topic = _message_to_sentry_thread_topic(message)
        notify_error(message=f'[Cloudcare] {thread_topic}', details=data)
    elif error_type == 'show_error_notification':
        message = data.get('message')
        thread_topic = _message_to_sentry_thread_topic(message)
        metrics_counter('commcare.formplayer.show_error_notification', tags={
            'message': _message_to_tag_value(message or 'no_message'),
            'domain': domain,
            'cloudcare_env': data.get('cloudcareEnv'),
        })
        notify_error(message=f'[Cloudcare] {thread_topic}', details=data)
    else:
        metrics_counter('commcare.formplayer.unknown_error_type', tags={
            'domain': domain,
            'cloudcare_env': data.get('cloudcareEnv'),
        })
        notify_error(message='[Cloudcare] unknown error type', details=data)
    return JsonResponse({'status': 'ok'})


@waf_allow('XSS_BODY')
@csrf_exempt
@location_safe
@login_and_domain_required
def report_sentry_error(request, domain):
    # code modified from Sentry example:
    # https://github.com/getsentry/examples/blob/master/tunneling/python/app.py

    try:
        envelope = request.body.decode("utf-8")
        json_lines = envelope.split("\n")
        header = json.loads(json_lines[0])
        if header.get("dsn") != settings.SENTRY_DSN:
            raise Exception(f"Invalid Sentry DSN: {header.get('dsn')}")

        dsn = urllib.parse.urlparse(header.get("dsn"))
        project_id = dsn.path.strip("/")
        if project_id != settings.SENTRY_DSN.split('/')[-1]:
            raise Exception(f"Invalid Sentry Project ID: {project_id}")

        url = f"https://{dsn.hostname}/api/{project_id}/envelope/"
        requests.post(url=url, data=envelope)
    except Exception:
        notify_exception(request, "Error sending frontend data to Sentry")

    return JsonResponse({})


def _message_to_tag_value(message, allowed_chars=string.ascii_lowercase + string.digits + '_'):
    """
    Turn a long user-facing error message into a short slug that can be used as a datadog tag value

    passes through unidecode to get something ascii-compatible to work with,
    then uses the first four space-delimited words and filters out unwanted characters.

    >>> _message_to_tag_value('Sorry, an error occurred while processing that request.')
    'sorry_an_error_occurred'
    >>> _message_to_tag_value('Another process prevented us from servicing your request. Please try again later.')
    'another_process_prevented_us'
    >>> _message_to_tag_value('509 Unknown Status Code')
    '509_unknown_status_code'
    >>> _message_to_tag_value(
    ... 'EntityScreen EntityScreen [Detail=org.commcare.suite.model.Detail@1f984e3c, '
    ... 'selection=null] could not select case 8854f3583f6f46e69af59fddc9f9428d. '
    ... 'If this error persists please report a bug to CommCare HQ.')
    'entityscreen_entityscreen_detail_org'
    """
    message_tag = unidecode(message)
    message_tag = ''.join((c if c in allowed_chars else ' ') for c in message_tag.lower())
    message_tag = '_'.join(re.split(r' +', message_tag)[:4])
    return message_tag[:59]


def _message_to_sentry_thread_topic(message):
    """
    >>> _message_to_sentry_thread_topic(
    ... 'EntityScreen EntityScreen [Detail=org.commcare.suite.model.Detail@1f984e3c, '
    ... 'selection=null] could not select case 8854f3583f6f46e69af59fddc9f9428d. '
    ... 'If this error persists please report a bug to CommCare HQ.')
    'EntityScreen EntityScreen [Detail=org.commcare.suite.model.Detail@[...], selection=null] could not select case [...]. If this error persists please report a bug to CommCare HQ.'
    """  # noqa: E501
    return re.sub(r'[a-f0-9-]{7,}', '[...]', message)


@login_and_domain_required
@require_cloudcare_access
@requires_privilege_for_commcare_user(privileges.CLOUDCARE)
@location_safe
def session_endpoint(request, domain, app_id, endpoint_id=None):
    def _fail(error):
        messages.error(request, error)
        return HttpResponseRedirect(reverse(FormplayerMain.urlname, args=[domain]))

    if not toggles.SESSION_ENDPOINTS.enabled_for_request(request):
        return _fail(_("Linking directly into Web Apps has been disabled."))

    build_id = _fetch_build_id(domain, request.couch_user.username, app_id)
    if not build_id:
        # These links can be used for cross-domain web apps workflows, where a link jumps to the
        # same screen but in another domain's corresponding app. This works if both the source and
        # target apps are downstream apps that share an upstream app - the link references the upstream app.
        from corehq.apps.linked_domain.applications import get_downstream_app_id_map
        id_map = get_downstream_app_id_map(domain)
        if app_id in id_map:
            if len(id_map[app_id]) == 1:
                build_id = _fetch_build_id(domain, request.couch_user.username, id_map[app_id][0])
            else:
                return _fail(_("Multiple corresponding applications found. Could not follow link."))
        if not build_id:
            return _fail(_("No corresponding application found in this project."))

    restore_as_user, set_cookie = FormplayerMain.get_restore_as_user(request, domain)
    force_login_as = not restore_as_user.is_commcare_user()
    if force_login_as and not can_use_restore_as(request):
        return _fail(_("This user cannot access this link."))

    state = {"appId": build_id, "forceLoginAs": force_login_as}
    if endpoint_id is not None:
        state.update({
            "endpointId": endpoint_id,
            "endpointArgs": {
                urllib.parse.quote_plus(key): urllib.parse.quote_plus(value)
                for key, value in request.GET.items()
            }
        })
    cloudcare_state = json.dumps(state)
    return HttpResponseRedirect(reverse(FormplayerMain.urlname, args=[domain]) + "#" + cloudcare_state)


class BlockWebAppsView(BaseDomainView):

    urlname = 'block_web_apps'
    template_name = 'cloudcare/block_web_apps.html'

    def get(self, request, *args, **kwargs):
        mobile_ucr_count = get_mobile_ucr_count(request.domain)
        context = self.get_context_for_ucr_limit_error(request.domain, mobile_ucr_count)
        return render(request, self.template_name, context)

    @staticmethod
    def get_context_for_ucr_limit_error(domain, mobile_ucr_count):
        return {
            'domain': domain,
            'ucr_limit': settings.MAX_MOBILE_UCR_LIMIT,
            'error_message': _("""You have the MOBILE_UCR feature flag enabled, and have {ucr_count} mobile UCRs
                               which exceeds the maximum limit of {ucr_limit} total User Configurable Reports used
                               across all of your applications. To resolve, you must remove references to UCRs in
                               your applications until you are under the limit. If you believe this is a mistake,
                               please reach out to support.
                            """).format(ucr_count=mobile_ucr_count, ucr_limit=settings.MAX_MOBILE_UCR_LIMIT)
        }


@login_and_domain_required
@require_POST
def api_histogram_metrics(request, domain):
    request_dict = request.POST

    metric_name = request_dict.get("metrics")
    duration = float(request_dict.get("responseTime"))

    if metric_name and duration:
        metrics_histogram(metric_name,
                          duration,
                          bucket_tag='duration_bucket',
                          buckets=(1000, 2000, 5000),
                          bucket_unit='ms',
                          tags={'domain': domain})
    return HttpResponse("Success!!")
