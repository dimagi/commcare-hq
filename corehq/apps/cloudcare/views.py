import HTMLParser
import json
from xml.etree import ElementTree

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.cache import cache_page
from django.views.generic import View
from django.views.generic.base import TemplateView

from couchdbkit import ResourceConflict

from casexml.apps.case.models import CASE_STATUS_OPEN
from casexml.apps.case.xml import V2
from casexml.apps.phone.fixtures import generator
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import use_sqlite_backend
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import string_to_boolean
from dimagi.utils.web import json_response, get_url_base, json_handler
from touchforms.formplayer.api import DjangoAuth, get_raw_instance, sync_db
from touchforms.formplayer.models import EntrySession
from xml2json.lib import xml2json

from corehq import toggles, privileges
from corehq.apps.accounting.decorators import requires_privilege_for_commcare_user, requires_privilege_with_fallback
from corehq.apps.app_manager.dbaccessors import (
    get_latest_build_doc,
    get_brief_apps_in_domain,
    get_latest_released_app_doc,
    get_app_ids_in_domain,
    get_current_app,
    wrap_app,
    get_current_app_doc,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.exceptions import FormNotFoundException, ModuleNotFoundException
from corehq.apps.app_manager.models import Application, ApplicationBase, RemoteApp
from corehq.apps.app_manager.suite_xml.sections.details import get_instances_for_module
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.app_manager.util import get_cloudcare_session_data
from corehq.apps.locations.permissions import location_safe
from corehq.apps.cloudcare.api import (
    api_closed_to_status,
    CaseAPIResult,
    get_app_json,
    get_filtered_cases,
    get_filters_from_request_params,
    get_open_form_sessions,
    look_up_app_json,
)
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.cloudcare.decorators import require_cloudcare_access
from corehq.apps.cloudcare.exceptions import RemoteAppError
from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.apps.cloudcare.touchforms_api import BaseSessionDataHelper, CaseSessionDataHelper
from corehq.apps.cloudcare.const import WEB_APPS_ENVIRONMENT, PREVIEW_APP_ENVIRONMENT
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest_ex, domain_admin_required
from corehq.apps.groups.models import Group
from corehq.apps.reports.formdetails import readable
from corehq.apps.style.decorators import (
    use_datatables,
    use_legacy_jquery,
    use_jquery_ui,
)
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.users.views import BaseUserSettingsView
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors, LedgerAccessors
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.util.quickcache import skippable_quickcache
from corehq.util.xml_utils import indent_xml
from corehq.apps.analytics.tasks import track_clicked_preview_on_hubspot
from corehq.apps.analytics.utils import get_meta


@require_cloudcare_access
def default(request, domain):
    return HttpResponseRedirect(reverse('cloudcare_main', args=[domain, '']))


@use_legacy_jquery
def insufficient_privilege(request, domain, *args, **kwargs):
    context = {
        'domain': domain,
    }

    return render(request, "cloudcare/insufficient_privilege.html", context)


class CloudcareMain(View):

    @use_datatables
    @use_legacy_jquery
    @use_jquery_ui
    @method_decorator(require_cloudcare_access)
    @method_decorator(requires_privilege_for_commcare_user(privileges.CLOUDCARE))
    def dispatch(self, request, *args, **kwargs):
        return super(CloudcareMain, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, urlPath):
        try:
            preview = string_to_boolean(request.GET.get("preview", "false"))
        except ValueError:
            # this is typically only set at all if it's intended to be true so this
            # is a reasonable default for "something went wrong"
            preview = True

        app_access = ApplicationAccess.get_by_domain(domain)
        accessor = CaseAccessors(domain)

        if not preview:
            apps = get_cloudcare_apps(domain)
            if request.project.use_cloudcare_releases:

                if (toggles.CLOUDCARE_LATEST_BUILD.enabled(domain) or
                        toggles.CLOUDCARE_LATEST_BUILD.enabled(request.couch_user.username)):
                    get_cloudcare_app = get_latest_build_doc
                else:
                    get_cloudcare_app = get_latest_released_app_doc

                apps = map(
                    lambda app: get_cloudcare_app(domain, app['_id']),
                    apps,
                )
                apps = filter(None, apps)
                apps = map(wrap_app, apps)

                # convert to json
                apps = [get_app_json(app) for app in apps]
            else:
                # legacy functionality - use the latest build regardless of stars
                apps = [get_latest_build_doc(domain, app['_id']) for app in apps]
                apps = [get_app_json(ApplicationBase.wrap(app)) for app in apps if app]

        else:
            # big TODO: write a new apps view for Formplayer, can likely cut most out now
            if toggles.USE_FORMPLAYER_FRONTEND.enabled(domain):
                apps = get_cloudcare_apps(domain)
            else:
                apps = get_brief_apps_in_domain(domain)
            apps = [get_app_json(app) for app in apps if app and (
                isinstance(app, RemoteApp) or app.application_version == V2)]
            meta = get_meta(request)
            track_clicked_preview_on_hubspot(request.couch_user, request.COOKIES, meta)

        # trim out empty apps
        apps = filter(lambda app: app, apps)
        apps = filter(lambda app: app_access.user_can_access_app(request.couch_user, app), apps)

        def _default_lang():
            if apps:
                # unfortunately we have to go back to the DB to find this
                return Application.get(apps[0]["_id"]).default_language
            else:
                return "en"

        # default language to user's preference, followed by
        # first app's default, followed by english
        language = request.couch_user.language or _default_lang()

        def _url_context():
            # given a url path, returns potentially the app, parent, and case, if
            # they're selected. the front end optimizes with these to avoid excess
            # server calls

            # there's an annoying dependency between this logic and backbone's
            # url routing that seems hard to solve well. this needs to be synced
            # with apps.js if anything changes

            # for apps anything with "view/app/" works

            # for cases it will be:
            # "view/:app/:module/:form/case/:case/"

            # if there are parent cases, it will be:
            # "view/:app/:module/:form/parent/:parent/case/:case/

            # could use regex here but this is actually simpler with the potential
            # absence of a trailing slash
            split = urlPath.split('/')
            app_id = split[1] if len(split) >= 2 else None

            if len(split) >= 5 and split[4] == "parent":
                parent_id = split[5]
                case_id = split[7] if len(split) >= 7 else None
            else:
                parent_id = None
                case_id = split[5] if len(split) >= 6 else None

            app = None
            if app_id:
                if app_id in [a['_id'] for a in apps]:
                    app = look_up_app_json(domain, app_id)
                else:
                    messages.info(request, _("That app is no longer valid. Try using the "
                                             "navigation links to select an app."))
            if app is None and len(apps) == 1:
                app = look_up_app_json(domain, apps[0]['_id'])

            def _get_case(domain, case_id):
                case = accessor.get_case(case_id)
                assert case.domain == domain, "case %s not in %s" % (case_id, domain)
                return case.to_api_json()

            case = _get_case(domain, case_id) if case_id else None
            if parent_id is None and case is not None:
                parent_id = case.get('indices', {}).get('parent', {}).get('case_id', None)
            parent = _get_case(domain, parent_id) if parent_id else None

            return {
                "app": app,
                "case": case,
                "parent": parent
            }

        context = {
            "domain": domain,
            "language": language,
            "apps": apps,
            "apps_raw": apps,
            "preview": preview,
            "maps_api_key": settings.GMAPS_API_KEY,
            "sessions_enabled": request.couch_user.is_commcare_user(),
            "use_cloudcare_releases": request.project.use_cloudcare_releases,
            "username": request.user.username,
            "formplayer_url": settings.FORMPLAYER_URL,
            'use_sqlite_backend': use_sqlite_backend(domain),
        }
        context.update(_url_context())
        if toggles.USE_FORMPLAYER_FRONTEND.enabled(domain):
            return render(request, "cloudcare/formplayer_home.html", context)
        else:
            return render(request, "cloudcare/cloudcare_home.html", context)


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

    def get(self, request, domain):
        app_access = ApplicationAccess.get_by_domain(domain)
        app_ids = get_app_ids_in_domain(domain)

        apps = map(
            lambda app_id: self.fetch_app(domain, app_id),
            app_ids,
        )
        apps = filter(None, apps)
        apps = filter(lambda app: app.get('cloudcare_enabled') or self.preview, apps)
        apps = filter(lambda app: app_access.user_can_access_app(request.couch_user, app), apps)
        apps = sorted(apps, key=lambda app: app['name'])

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
            "maps_api_key": settings.GMAPS_API_KEY,
            "username": request.user.username,
            "formplayer_url": settings.FORMPLAYER_URL,
            "single_app_mode": False,
            "home_url": reverse(self.urlname, args=[domain]),
            "environment": WEB_APPS_ENVIRONMENT,
        }
        return render(request, "cloudcare/formplayer_home.html", context)


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

    form_name = form.name.values()[0]

    # make the name for the session we will use with the case and form
    session_name = u'{app} > {form}'.format(
        app=app.name,
        form=form_name,
    )

    if case_id:
        case = CaseAccessors(domain).get_case(case_id)
        session_name = u'{0} - {1}'.format(session_name, case.name)

    root_context = {
        'form_url': form_url,
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


def get_cases_vary_on(request, domain):
    request_params = request.GET

    return [
        request.couch_user.get_id
        if request.couch_user.is_commcare_user() else request_params.get('user_id', ''),
        request_params.get('ids_only', 'false'),
        request_params.get('case_id', ''),
        request_params.get('footprint', 'false'),
        request_params.get('closed', 'false'),
        json.dumps(get_filters_from_request_params(request_params)),
        domain,
    ]


def get_cases_skip_arg(request, domain):
    """
    When this function returns True, skippable_quickcache will not go to the cache for the result. By default,
    if neither of these params are passed into the function, nothing will be cached. Cache will always be
    skipped if ids_only is false.

    The caching is mainly a hack for touchforms to respond more quickly. Touchforms makes repeated requests to
    get the list of case_ids associated with a user.
    """
    if not toggles.CLOUDCARE_CACHE.enabled(domain):
        return True
    request_params = request.GET
    return (not string_to_boolean(request_params.get('use_cache', 'false')) or
        not string_to_boolean(request_params.get('ids_only', 'false')))


@cloudcare_api
@skippable_quickcache(get_cases_vary_on, get_cases_skip_arg, timeout=240 * 60)
def get_cases(request, domain):
    request_params = request.GET

    if request.couch_user.is_commcare_user():
        user_id = request.couch_user.get_id
    else:
        user_id = request_params.get("user_id", "")

    if not user_id and not request.couch_user.is_web_user():
        return HttpResponseBadRequest("Must specify user_id!")

    ids_only = string_to_boolean(request_params.get("ids_only", "false"))
    case_id = request_params.get("case_id", "")
    footprint = string_to_boolean(request_params.get("footprint", "false"))
    accessor = CaseAccessors(domain)

    if toggles.HSPH_HACK.enabled(domain):
        hsph_case_id = request_params.get('hsph_hack', None)
        if hsph_case_id != 'None' and hsph_case_id and user_id:
            case = accessor.get_case(hsph_case_id)
            usercase_id = CommCareUser.get_by_user_id(user_id).get_usercase_id()
            usercase = accessor.get_case(usercase_id) if usercase_id else None
            return json_response(map(
                lambda case: CaseAPIResult(domain=domain, id=case['_id'], couch_doc=case, id_only=ids_only),
                filter(None, [case, case.parent, usercase])
            ))

    if case_id and not footprint:
        # short circuit everything else and just return the case
        # NOTE: this allows any user in the domain to access any case given
        # they know its ID, which is slightly different from the previous
        # behavior (can only access things you own + footprint). If we want to
        # change this contract we would need to update this to check the
        # owned case list + footprint
        case = accessor.get_case(case_id)
        assert case.domain == domain
        cases = [CaseAPIResult(domain=domain, id=case_id, couch_doc=case, id_only=ids_only)]
    else:
        filters = get_filters_from_request_params(request_params)
        status = api_closed_to_status(request_params.get('closed', 'false'))
        case_type = filters.get('properties/case_type', None)
        cases = get_filtered_cases(domain, status=status, case_type=case_type,
                                   user_id=user_id, filters=filters,
                                   footprint=footprint, ids_only=ids_only,
                                   strip_history=True)
    return json_response(cases)


@cloudcare_api
def filter_cases(request, domain, app_id, module_id, parent_id=None):
    app = Application.get(app_id)
    module = app.get_module(module_id)
    auth_cookie = request.COOKIES.get('sessionid')
    requires_parent_cases = string_to_boolean(request.GET.get('requires_parent_cases', 'false'))

    xpath = EntriesHelper.get_filter_xpath(module)
    instances = get_instances_for_module(app, module, additional_xpaths=[xpath])
    extra_instances = [{'id': inst.id, 'src': inst.src} for inst in instances]
    accessor = CaseAccessors(domain)

    # touchforms doesn't like this to be escaped
    xpath = HTMLParser.HTMLParser().unescape(xpath)
    case_type = module.case_type

    if xpath or should_use_sql_backend(domain):
        # if we need to do a custom filter, send it to touchforms for processing
        additional_filters = {
            "properties/case_type": case_type,
            "footprint": True
        }

        helper = BaseSessionDataHelper(domain, request.couch_user)
        result = helper.filter_cases(xpath, additional_filters, DjangoAuth(auth_cookie),
                                     extra_instances=extra_instances)
        if result.get('status', None) == 'error':
            code = result.get('code', 500)
            message = result.get('message', _("Something went wrong filtering your cases."))
            if code == 500:
                notify_exception(None, message=message)
            return json_response(message, status_code=code)

        case_ids = result.get("cases", [])
    else:
        # otherwise just use our built in api with the defaults
        case_ids = [res.id for res in get_filtered_cases(
            domain,
            status=CASE_STATUS_OPEN,
            case_type=case_type,
            user_id=request.couch_user._id,
            footprint=True,
            ids_only=True,
        )]

    cases = accessor.get_cases(case_ids)

    if parent_id:
        cases = filter(lambda c: c.parent and c.parent.case_id == parent_id, cases)

    # refilter these because we might have accidentally included footprint cases
    # in the results from touchforms. this is a little hacky but the easiest
    # (quick) workaround. should be revisted when we optimize the case list.
    cases = filter(lambda c: c.type == case_type, cases)
    cases = [c.to_api_json(lite=True) for c in cases if c]

    response = {'cases': cases}
    if requires_parent_cases:
        # Subtract already fetched cases from parent list
        parent_ids = set(map(lambda c: c['indices']['parent']['case_id'], cases)) - \
            set(map(lambda c: c['case_id'], cases))
        parents = accessor.get_cases(list(parent_ids))
        parents = [c.to_api_json(lite=True) for c in parents]
        response.update({'parents': parents})

    return json_response(response)


@cloudcare_api
def get_apps_api(request, domain):
    return json_response(get_cloudcare_apps(domain))


@cloudcare_api
def get_app_api(request, domain, app_id):
    try:
        return json_response(look_up_app_json(domain, app_id))
    except RemoteAppError:
        raise Http404()


@cloudcare_api
@cache_page(60 * 30)
def get_fixtures(request, domain, user_id, fixture_id=None):
    try:
        user = CommCareUser.get_by_user_id(user_id)
    except CouchUser.AccountTypeError:
        err = ("You can't use case sharing or fixtures as a %s. " 
               "Login as a mobile worker and try again.") % settings.WEB_USER_TERM,
        return HttpResponse(err, status=412, content_type="text/plain")
    
    if not user:
        raise Http404

    assert user.is_member_of(domain)
    restore_user = user.to_ota_restore_user()
    if not fixture_id:
        ret = ElementTree.Element("fixtures")
        for fixture in generator.get_fixtures(restore_user, version=V2):
            ret.append(fixture)
        return HttpResponse(ElementTree.tostring(ret), content_type="text/xml")
    else:
        fixture = generator.get_fixture_by_id(fixture_id, restore_user, version=V2)
        if not fixture:
            raise Http404
        assert len(fixture.getchildren()) == 1, 'fixture {} expected 1 child but found {}'.format(
            fixture_id, len(fixture.getchildren())
        )
        return HttpResponse(ElementTree.tostring(fixture.getchildren()[0]), content_type="text/xml")


@cloudcare_api
def get_sessions(request, domain):
    # is it ok to pull user from the request? other api calls seem to have an explicit 'user' param
    skip = request.GET.get('skip') or 0
    limit = request.GET.get('limit') or 10
    return json_response(get_open_form_sessions(request.user, skip=skip, limit=limit))


@cloudcare_api
def get_session_context(request, domain, session_id):
    # NOTE: although this view does not appeared to be called from anywhere it is, and cannot be deleted.
    # The javascript routing in cloudcare depends on it, though constructs it manually in a hardcoded way.
    # see getSessionContextUrl in cloudcare/util.js
    # Adding 'cloudcare_get_session_context' to this comment so that the url name passes a grep test
    try:
        session = EntrySession.objects.get(session_id=session_id)
    except EntrySession.DoesNotExist:
        session = None
    if request.method == 'DELETE':
        if session:
            session.delete()
        return json_response({'status': 'success'})
    else:
        helper = BaseSessionDataHelper(domain, request.couch_user)
        return json_response(helper.get_full_context({
            'session_id': session_id,
            'app_id': session.app_id if session else None
        }))


@cloudcare_api
def get_ledgers(request, domain):
    """
    Returns ledgers associated with a case in the format:
    {
        "section_id": {
            "product_id": amount,
            "product_id": amount,
            ...
        },
        ...
    }

    Note: this only works for the Couch backend
    """
    request_params = request.GET
    case_id = request_params.get('case_id')
    if not case_id:
        return json_response(
            {'message': 'You must specify a case id to make this query.'},
            status_code=400
        )
    try:
        case = CaseAccessors(domain).get_case(case_id)
    except CaseNotFound:
        raise Http404()
    ledger_map = LedgerAccessors(domain).get_case_ledger_state(case.case_id)
    def custom_json_handler(obj):
        if hasattr(obj, 'stock_on_hand'):
            return obj.stock_on_hand
        return json_handler(obj)

    return json_response(
        {
            'entity_id': case_id,
            'ledger': ledger_map,
        },
        default=custom_json_handler,
    )


@cloudcare_api
def sync_db_api(request, domain):
    auth_cookie = request.COOKIES.get('sessionid')
    username = request.GET.get('username')
    try:
        response = sync_db(username, domain, DjangoAuth(auth_cookie))
    except Exception, e:
        return json_response(
            {'status': 'error', 'message': unicode(e)},
            status_code=500
        )
    else:
        return json_response(response)


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


@cloudcare_api
def render_form(request, domain):
    # get session
    session_id = request.GET.get('session_id')

    session = get_object_or_404(EntrySession, session_id=session_id)

    try:
        raw_instance = get_raw_instance(session_id, domain)
    except Exception, e:
        return HttpResponse(e, status=500, content_type="text/plain")

    xmlns = raw_instance["xmlns"]
    form_data_xml = raw_instance["output"]

    _, form_data_json = xml2json(form_data_xml)
    pretty_questions = readable.get_questions(domain, session.app_id, xmlns)

    readable_form = readable.get_readable_form_data(form_data_json, pretty_questions)

    rendered_readable_form = render_to_string(
        'reports/form/partials/readable_form.html',
        {'questions': readable_form}
    )

    return json_response({
        'form_data': rendered_readable_form,
        'instance_xml': indent_xml(form_data_xml)
    })


class HttpResponseConflict(HttpResponse):
    status_code = 409


class EditCloudcareUserPermissionsView(BaseUserSettingsView):
    template_name = 'cloudcare/config.html'
    urlname = 'cloudcare_app_settings'

    @property
    def page_title(self):
        if toggles.USE_FORMPLAYER_FRONTEND.enabled(self.domain):
            return _("Web Apps Permissions")
        else:
            return _("CloudCare Permissions")

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
        j = json.loads(request.body)
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
