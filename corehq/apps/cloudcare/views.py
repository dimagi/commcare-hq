from couchdbkit import ResourceConflict, ResourceNotFound
from django.utils.decorators import method_decorator
from casexml.apps.stock.models import StockTransaction
from casexml.apps.stock.utils import get_current_ledger_transactions
from corehq.apps.accounting.decorators import requires_privilege_for_commcare_user, requires_privilege_with_fallback
from corehq.apps.app_manager.exceptions import FormNotFoundException, ModuleNotFoundException
from corehq.apps.app_manager.util import is_usercase_in_use, get_cloudcare_session_data
from corehq.util.couch import get_document_or_404
from corehq.util.quickcache import skippable_quickcache
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from django.views.decorators.cache import cache_page
from casexml.apps.case.models import CommCareCase
from corehq import toggles, privileges
from corehq.apps.app_manager.suite_xml import SuiteGenerator
from corehq.apps.cloudcare.exceptions import RemoteAppError
from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.apps.cloudcare.touchforms_api import SessionDataHelper
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest_ex, domain_admin_required
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.users.views import BaseUserSettingsView
from dimagi.utils.web import json_response, get_url_base, json_handler
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest, Http404
from django.shortcuts import render
from django.template.loader import render_to_string
from corehq.apps.app_manager.models import Application, ApplicationBase, get_app
import json
from corehq.apps.cloudcare.api import look_up_app_json, get_cloudcare_apps, get_filtered_cases, get_filters_from_request,\
    api_closed_to_status, CaseAPIResult, CASE_STATUS_OPEN, get_app_json, get_open_form_sessions
from dimagi.utils.parsing import string_to_boolean
from dimagi.utils.logging import notify_exception
from django.conf import settings
from touchforms.formplayer.api import DjangoAuth
from django.core.urlresolvers import reverse
from casexml.apps.phone.fixtures import generator
from casexml.apps.case.xml import V2
from xml.etree import ElementTree
from corehq.apps.cloudcare.decorators import require_cloudcare_access
import HTMLParser
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_noop
from touchforms.formplayer.models import EntrySession
from xml2json.lib import xml2json
import requests
from corehq.apps.reports.formdetails import readable
from corehq.apps.reports.templatetags.xform_tags import render_pretty_xml
from django.shortcuts import get_object_or_404


@require_cloudcare_access
def default(request, domain):
    return HttpResponseRedirect(reverse('cloudcare_main', args=[domain, '']))

def insufficient_privilege(request, domain, *args, **kwargs):
    context = {
        'domain': domain,
    }

    return render(request, "cloudcare/insufficient_privilege.html", context)

@require_cloudcare_access
@requires_privilege_for_commcare_user(privileges.CLOUDCARE)
def cloudcare_main(request, domain, urlPath):
    try:
        preview = string_to_boolean(request.REQUEST.get("preview", "false"))
    except ValueError:
        # this is typically only set at all if it's intended to be true so this
        # is a reasonable default for "something went wrong"
        preview = True

    app_access = ApplicationAccess.get_by_domain(domain)

    if not preview:
        apps = get_cloudcare_apps(domain)
        if request.project.use_cloudcare_releases:
            # replace the apps with the last starred build of each app, removing the ones that aren't starred
            apps = filter(lambda app: app.is_released, [get_app(domain, app['_id'], latest=True) for app in apps])
            # convert to json
            apps = [get_app_json(app) for app in apps]
        else:
            # legacy functionality - use the latest build regardless of stars
            apps = [get_app_json(ApplicationBase.get_latest_build(domain, app['_id'])) for app in apps]

    else:
        apps = ApplicationBase.view('app_manager/applications_brief', startkey=[domain], endkey=[domain, {}])
        apps = [get_app_json(app) for app in apps if app and app.application_version == V2]

    # trim out empty apps
    apps = filter(lambda app: app, apps)
    apps = filter(lambda app: app_access.user_can_access_app(request.couch_user, app), apps)
    
    def _default_lang():
        if apps:
            # unfortunately we have to go back to the DB to find this
            return Application.get(apps[0]["_id"]).build_langs[0]
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
            case = CommCareCase.get(case_id)
            assert case.domain == domain, "case %s not in %s" % (case_id, domain)
            return case.get_json()

        case = _get_case(domain, case_id) if case_id else None
        if parent_id is None and case is not None:
            parent_id = case.get('indices',{}).get('parent', {}).get('case_id', None)
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
       'offline_enabled': toggles.OFFLINE_CLOUDCARE.enabled(request.user.username),
       'sessions_enabled': request.couch_user.is_commcare_user(),
       'use_cloudcare_releases': request.project.use_cloudcare_releases,
    }
    context.update(_url_context())
    return render(request, "cloudcare/cloudcare_home.html", context)

@login_and_domain_required
@requires_privilege_for_commcare_user(privileges.CLOUDCARE)
def form_context(request, domain, app_id, module_id, form_id):
    app = Application.get(app_id)
    form_url = "%s%s" % (get_url_base(), reverse('download_xform', args=[domain, app_id, module_id, form_id]))
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
        session_name = u'{0} - {1}'.format(session_name, CommCareCase.get(case_id).name)

    root_context = {
        'form_url': form_url,
    }
    if instance_id:
        try:
            root_context['instance_xml'] = XFormInstance.get_db().fetch_attachment(
                instance_id, ATTACHMENT_NAME
            )
        except ResourceNotFound:
            raise Http404()


    session_extras = {'session_name': session_name, 'app_id': app._id}
    suite_gen = SuiteGenerator(app, is_usercase_in_use(domain))
    session_extras.update(get_cloudcare_session_data(suite_gen, domain, form, request.couch_user))

    delegation = request.GET.get('task-list') == 'true'
    offline = request.GET.get('offline') == 'true'
    session_helper = SessionDataHelper(domain, request.couch_user, case_id, delegation=delegation, offline=offline)
    return json_response(session_helper.get_full_context(
        root_context,
        session_extras
    ))


cloudcare_api = login_or_digest_ex(allow_cc_users=True)


def get_cases_vary_on(request, domain):
    return [
        request.couch_user.get_id
        if request.couch_user.is_commcare_user() else request.REQUEST.get('user_id', ''),
        request.REQUEST.get('ids_only', 'false'),
        request.REQUEST.get('case_id', ''),
        request.REQUEST.get('footprint', 'false'),
        request.REQUEST.get('include_children', 'false'),
        request.REQUEST.get('closed', 'false'),
        json.dumps(get_filters_from_request(request)),
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
    return (not string_to_boolean(request.REQUEST.get('use_cache', 'false')) or
        not string_to_boolean(request.REQUEST.get('ids_only', 'false')))


@cloudcare_api
@skippable_quickcache(get_cases_vary_on, get_cases_skip_arg, timeout=240 * 60)
def get_cases(request, domain):
    if request.couch_user.is_commcare_user():
        user_id = request.couch_user.get_id
    else:
        user_id = request.REQUEST.get("user_id", "")

    if not user_id and not request.couch_user.is_web_user():
        return HttpResponseBadRequest("Must specify user_id!")

    ids_only = string_to_boolean(request.REQUEST.get("ids_only", "false"))
    case_id = request.REQUEST.get("case_id", "")
    footprint = string_to_boolean(request.REQUEST.get("footprint", "false"))
    include_children = string_to_boolean(request.REQUEST.get("include_children", "false"))
    if case_id and not footprint and not include_children:
        # short circuit everything else and just return the case
        # NOTE: this allows any user in the domain to access any case given
        # they know its ID, which is slightly different from the previous
        # behavior (can only access things you own + footprint). If we want to
        # change this contract we would need to update this to check the
        # owned case list + footprint
        case = CommCareCase.get(case_id)
        assert case.domain == domain
        cases = [CaseAPIResult(id=case_id, couch_doc=case, id_only=ids_only)]
    else:
        filters = get_filters_from_request(request)
        status = api_closed_to_status(request.REQUEST.get('closed', 'false'))
        case_type = filters.get('properties/case_type', None)
        cases = get_filtered_cases(domain, status=status, case_type=case_type,
                                   user_id=user_id, filters=filters,
                                   footprint=footprint, ids_only=ids_only,
                                   strip_history=True, include_children=include_children)
    return json_response(cases)

@cloudcare_api
def filter_cases(request, domain, app_id, module_id, parent_id=None):
    app = Application.get(app_id)
    module = app.get_module(module_id)
    auth_cookie = request.COOKIES.get('sessionid')

    suite_gen = SuiteGenerator(app, is_usercase_in_use(domain))
    xpath = suite_gen.get_filter_xpath(module)
    extra_instances = [{'id': inst.id, 'src': inst.src}
                       for inst in suite_gen.get_instances_for_module(module, additional_xpaths=[xpath])]

    # touchforms doesn't like this to be escaped
    xpath = HTMLParser.HTMLParser().unescape(xpath)
    case_type = module.case_type

    if xpath:
        # if we need to do a custom filter, send it to touchforms for processing
        additional_filters = {
            "properties/case_type": case_type,
            "footprint": True
        }

        helper = SessionDataHelper(domain, request.couch_user)
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

    cases = [CommCareCase.wrap(doc) for doc in iter_docs(CommCareCase.get_db(), case_ids)]

    if parent_id:
        cases = filter(lambda c: c.parent and c.parent.case_id == parent_id, cases)

    # refilter these because we might have accidentally included footprint cases
    # in the results from touchforms. this is a little hacky but the easiest
    # (quick) workaround. should be revisted when we optimize the case list.
    cases = filter(lambda c: c.type == case_type, cases)
    cases = [c.get_json(lite=True) for c in cases if c]

    return json_response(cases)

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
    casexml_user = user.to_casexml_user()
    if not fixture_id:
        ret = ElementTree.Element("fixtures")
        for fixture in generator.get_fixtures(casexml_user, version=V2):
            ret.append(fixture)
        return HttpResponse(ElementTree.tostring(ret), content_type="text/xml")
    else:
        fixture = generator.get_fixture_by_id(fixture_id, casexml_user, version=V2)
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
    try:
        session = EntrySession.objects.get(session_id=session_id)
    except EntrySession.DoesNotExist:
        session = None
    if request.method == 'DELETE':
        if session:
            session.delete()
        return json_response({'status': 'success'})
    else:
        helper = SessionDataHelper(domain, request.couch_user)
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
    """
    case_id = request.REQUEST.get('case_id')
    if not case_id:
        return json_response(
            {'message': 'You must specify a case id to make this query.'},
            status_code=400
        )
    case = get_document_or_404(CommCareCase, domain, case_id)
    ledger_map = get_current_ledger_transactions(case._id)
    def custom_json_handler(obj):
        if isinstance(obj, StockTransaction):
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
def render_form(request, domain):
    # get session
    session_id = request.GET.get('session_id')

    session = get_object_or_404(EntrySession, session_id=session_id)

    response = requests.post("{base_url}/webforms/get-xml/{session_id}".format(
        base_url=get_url_base(),
        session_id=session_id)
    )

    if response.status_code is not 200:
        err = "Session XML could not be found"
        return HttpResponse(err, status=500, content_type="text/plain")

    response_json = json.loads(response.text)
    xmlns = response_json["xmlns"]
    form_data_xml = response_json["output"]

    _, form_data_json = xml2json(form_data_xml)
    pretty_questions = readable.get_questions(domain, session.app_id, xmlns)

    readable_form = readable.get_readable_form_data(form_data_json, pretty_questions)

    rendered_readable_form = render_to_string(
        'reports/form/partials/readable_form.html',
        {'questions': readable_form}
    )

    return json_response({
        'form_data': rendered_readable_form,
        'instance_xml': render_pretty_xml(form_data_xml)
    })


class HttpResponseConflict(HttpResponse):
    status_code = 409


class EditCloudcareUserPermissionsView(BaseUserSettingsView):
    template_name = 'cloudcare/config.html'
    urlname = 'cloudcare_app_settings'
    page_title = ugettext_noop("CloudCare Permissions")

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
