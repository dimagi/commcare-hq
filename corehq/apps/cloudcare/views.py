from __future__ import absolute_import
from __future__ import unicode_literals
import json
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
from xml.etree import cElementTree as ElementTree

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest, Http404, \
    JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_page
from django.views.generic import View
from django.views.generic.base import TemplateView

from couchdbkit import ResourceConflict

from casexml.apps.phone.fixtures import generator
from corehq.apps.users.util import format_username
from dimagi.utils.parsing import string_to_boolean
from dimagi.utils.web import json_response, get_url_base
from xml2json.lib import xml2json

from corehq import toggles, privileges
from corehq.apps.accounting.decorators import requires_privilege_for_commcare_user, requires_privilege_with_fallback
from corehq.apps.accounting.utils import domain_is_on_trial
from corehq.apps.app_manager.dbaccessors import (
    get_latest_build_doc,
    get_latest_released_app_doc,
    get_app_ids_in_domain,
    get_current_app,
    get_current_app_doc,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.exceptions import FormNotFoundException, ModuleNotFoundException
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import get_cloudcare_session_data
from corehq.apps.locations.permissions import location_safe
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.cloudcare.esaccessors import login_as_user_query
from corehq.apps.cloudcare.decorators import require_cloudcare_access
from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.apps.cloudcare.touchforms_api import CaseSessionDataHelper
from corehq.apps.cloudcare.const import WEB_APPS_ENVIRONMENT, PREVIEW_APP_ENVIRONMENT
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest_ex, domain_admin_required
from corehq.apps.groups.models import Group
from corehq.apps.reports.formdetails import readable
from corehq.apps.hqwebapp.decorators import (
    use_datatables,
    use_legacy_jquery,
    use_jquery_ui,
)
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.exceptions import XFormNotFound
from six.moves import filter
from six.moves import map


@require_cloudcare_access
def default(request, domain):
    return HttpResponseRedirect(reverse('formplayer_main', args=[domain]))


@location_safe
class FormplayerMain(View):

    preview = False
    urlname = 'formplayer_main'

    @use_datatables
    @use_legacy_jquery
    @use_jquery_ui
    @method_decorator(require_cloudcare_access)
    @method_decorator(requires_privilege_for_commcare_user(privileges.CLOUDCARE))
    def dispatch(self, request, *args, **kwargs):
        return super(FormplayerMain, self).dispatch(request, *args, **kwargs)

    def fetch_app(self, domain, app_id):
        username = self.request.couch_user.username
        if (toggles.CLOUDCARE_LATEST_BUILD.enabled(domain) or
                toggles.CLOUDCARE_LATEST_BUILD.enabled(username)):
            return get_latest_build_doc(domain, app_id)
        else:
            return get_latest_released_app_doc(domain, app_id)

    def get_web_apps_available_to_user(self, domain, user):
        app_access = ApplicationAccess.get_by_domain(domain)
        app_ids = get_app_ids_in_domain(domain)

        apps = list(map(
            lambda app_id: self.fetch_app(domain, app_id),
            app_ids,
        ))
        apps = filter(None, apps)
        apps = filter(lambda app: app.get('cloudcare_enabled') or self.preview, apps)
        apps = filter(lambda app: app_access.user_can_access_app(user, app), apps)
        role = user.get_role(domain)
        if role:
            apps = [app for app in apps if role.permissions.view_web_app(app)]
        apps = sorted(apps, key=lambda app: app['name'])
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

        cookie_name = six.moves.urllib.parse.quote(
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

        return request.couch_user, set_cookie

    def get(self, request, domain):
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

        context = {
            "domain": domain,
            "language": language,
            "apps": apps,
            "domain_is_on_trial": domain_is_on_trial(domain),
            "maps_api_key": settings.GMAPS_API_KEY,
            "username": request.couch_user.username,
            "formplayer_url": settings.FORMPLAYER_URL,
            "single_app_mode": False,
            "home_url": reverse(self.urlname, args=[domain]),
            "environment": WEB_APPS_ENVIRONMENT,
            'use_live_query': toggles.FORMPLAYER_USE_LIVEQUERY.enabled(domain),
        }
        return set_cookie(
            render(request, "cloudcare/formplayer_home.html", context)
        )


class FormplayerMainPreview(FormplayerMain):

    preview = True
    urlname = 'formplayer_main_preview'

    @use_legacy_jquery
    def dispatch(self, request, *args, **kwargs):
        return super(FormplayerMain, self).dispatch(request, *args, **kwargs)

    def fetch_app(self, domain, app_id):
        return get_current_app_doc(domain, app_id)


class FormplayerPreviewSingleApp(View):

    urlname = 'formplayer_single_app'

    @use_datatables
    @use_legacy_jquery
    @use_jquery_ui
    @method_decorator(require_cloudcare_access)
    @method_decorator(requires_privilege_for_commcare_user(privileges.CLOUDCARE))
    def dispatch(self, request, *args, **kwargs):
        return super(FormplayerPreviewSingleApp, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, app_id, **kwargs):
        app_access = ApplicationAccess.get_by_domain(domain)

        app = get_current_app(domain, app_id)

        if not app_access.user_can_access_app(request.couch_user, app):
            raise Http404()

        role = request.couch_user.get_role(domain)
        if role and not role.permissions.view_web_app(app):
            raise Http404()

        def _default_lang():
            try:
                return app['langs'][0]
            except Exception:
                return 'en'

        # default language to user's preference, followed by
        # first app's default, followed by english
        language = request.couch_user.language or _default_lang()

        context = {
            "domain": domain,
            "language": language,
            "apps": [app],
            "maps_api_key": settings.GMAPS_API_KEY,
            "username": request.user.username,
            "formplayer_url": settings.FORMPLAYER_URL,
            "single_app_mode": True,
            "home_url": reverse(self.urlname, args=[domain, app_id]),
            "environment": WEB_APPS_ENVIRONMENT,
            'use_live_query': toggles.FORMPLAYER_USE_LIVEQUERY.enabled(domain),
        }
        return render(request, "cloudcare/formplayer_home.html", context)


class PreviewAppView(TemplateView):
    template_name = 'preview_app/base.html'
    urlname = 'preview_app'

    @use_legacy_jquery
    def get(self, request, *args, **kwargs):
        app = get_app(request.domain, kwargs.pop('app_id'))
        return self.render_to_response({
            'app': app,
            'formplayer_url': settings.FORMPLAYER_URL,
            "maps_api_key": settings.GMAPS_API_KEY,
            "environment": PREVIEW_APP_ENVIRONMENT,
        })


@location_safe
class LoginAsUsers(View):

    http_method_names = ['get']
    urlname = 'login_as_users'

    @method_decorator(login_and_domain_required)
    @method_decorator(require_can_edit_commcare_users)
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
        user_data_fields = []
        return login_as_user_query(
            self.domain,
            self.couch_user,
            search_string,
            limit,
            page * limit,
            user_data_fields=user_data_fields
        )

    def _format_user(self, user_json):
        user = CouchUser.wrap_correctly(user_json)
        formatted_user = {
            'username': user.raw_username,
            'customFields': user.user_data,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phoneNumbers': user.phone_numbers,
            'user_id': user.user_id,
            'location': user.sql_location.to_json() if user.sql_location else None,
        }
        return formatted_user


@login_and_domain_required
@requires_privilege_for_commcare_user(privileges.CLOUDCARE)
def form_context(request, domain, app_id, module_id, form_id):
    app = Application.get(app_id)
    form_url = '{}{}'.format(
        settings.CLOUDCARE_BASE_URL or get_url_base(),
        reverse('download_xform', args=[domain, app_id, module_id, form_id])
    )
    case_id = request.GET.get('case_id')
    instance_id = request.GET.get('instance_id')
    try:
        form = app.get_module(module_id).get_form(form_id)
    except (FormNotFoundException, ModuleNotFoundException):
        raise Http404()

    form_name = list(form.name.values())[0]

    # make the name for the session we will use with the case and form
    session_name = '{app} > {form}'.format(
        app=app.name,
        form=form_name,
    )

    if case_id:
        case = CaseAccessors(domain).get_case(case_id)
        session_name = '{0} - {1}'.format(session_name, case.name)

    root_context = {
        'form_url': form_url,
        'formplayer_url': settings.FORMPLAYER_URL,
    }
    if instance_id:
        try:
            root_context['instance_xml'] = FormAccessors(domain).get_form(instance_id).get_xml()
        except XFormNotFound:
            raise Http404()

    session_extras = {'session_name': session_name, 'app_id': app._id}
    session_extras.update(get_cloudcare_session_data(domain, form, request.couch_user))

    delegation = request.GET.get('task-list') == 'true'
    session_helper = CaseSessionDataHelper(domain, request.couch_user, case_id, app, form, delegation=delegation)
    return json_response(session_helper.get_full_context(
        root_context,
        session_extras
    ))


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

    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.CLOUDCARE))
    def dispatch(self, request, *args, **kwargs):
        return super(EditCloudcareUserPermissionsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        apps = get_cloudcare_apps(self.domain)
        access = ApplicationAccess.get_template_json(self.domain, apps)
        groups = Group.by_domain(self.domain)
        return {
            'apps': apps,
            'groups': groups,
            'access': access,
        }

    def put(self, request, *args, **kwargs):
        j = json.loads(request.body.decode('utf-8'))
        old = ApplicationAccess.get_by_domain(self.domain)
        new = ApplicationAccess.wrap(j)
        old.restrict = new.restrict
        old.app_groups = new.app_groups
        try:
            if old._rev != new._rev or old._id != new._id:
                raise ResourceConflict()
            old.save()
        except ResourceConflict:
            return HttpResponseConflict()
        else:
            return json_response({'_rev': old._rev})
