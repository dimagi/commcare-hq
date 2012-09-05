from casexml.apps.case.models import CommCareCase
from corehq.apps.cloudcare.models import CaseSpec
from corehq.apps.domain.decorators import login_and_domain_required,\
    login_or_digest_ex
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, CommCareUser
from dimagi.utils.decorators import inline
from dimagi.utils.web import render_to_response, json_response, json_handler
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseBadRequest, Http404
from corehq.apps.app_manager.models import Application, ApplicationBase
import json
from corehq.apps.cloudcare.api import get_owned_cases, get_app, get_cloudcare_apps, get_filtered_cases
from dimagi.utils.parsing import string_to_boolean
from django.conf import settings
from corehq.apps.cloudcare import touchforms_api 
from touchforms.formplayer.api import DjangoAuth
from django.core.urlresolvers import reverse
from casexml.apps.phone.fixtures import generator
from casexml.apps.case.xml import V2
from xml.etree import ElementTree
from corehq.apps.cloudcare.decorators import require_cloudcare_access
import HTMLParser

@require_cloudcare_access
def default(request, domain):
    return HttpResponseRedirect(reverse('cloudcare_app_list', args=[domain, '']))

@login_and_domain_required
def app_list(request, domain, urlPath):
    preview = string_to_boolean(request.REQUEST.get("preview", "false"))
    language = request.couch_user.language or "en"
    
    def _app_latest_build_json(app_id):
        build = ApplicationBase.view('app_manager/saved_app',
                                     startkey=[domain, app["_id"], {}],
                                     endkey=[domain, app["_id"]],
                                     descending=True,
                                     limit=1).one()
        return build._doc if build else None
                                     
    if not preview:
        apps = get_cloudcare_apps(domain)
        # replace the apps with the last build of each app
        apps = [_app_latest_build_json(app["_id"])for app in apps]
    
    else:
        apps = ApplicationBase.view('app_manager/applications_brief', startkey=[domain], endkey=[domain, {}])
        apps = [app._doc for app in apps if app and app.application_version == "2.0"]
    
    # trim out empty apps
    apps = filter(lambda app: app, apps)
    return render_to_response(request, "cloudcare/cloudcare_home.html", 
                              {"domain": domain,
                               "language": language,
                               "apps": json.dumps(apps),
                               "apps_raw": apps,
                               "preview": preview,
                               "maps_api_key": settings.GMAPS_API_KEY })


@login_and_domain_required
def form_context(request, domain, app_id, module_id, form_id):
    app = Application.get(app_id)
    module = app.get_module(module_id)
    form = module.get_form(form_id)
    case_id = request.REQUEST.get("case_id")
    return json_response(
        touchforms_api.get_full_context(domain, request.couch_user, 
                                        app, module, form, case_id))
        
@login_and_domain_required
def case_list(request, domain):
    
    apps = filter(lambda app: app.doc_type == "Application",
                  ApplicationBase.view('app_manager/applications_brief', 
                                       startkey=[domain], endkey=[domain, {}]))
    
    user_id = request.REQUEST.get("user_id", request.couch_user.get_id)
    app_id = request.REQUEST.get("app_id", "")
    module_id = int(request.REQUEST.get("module_id", "0"))
    language = request.REQUEST.get("language", "en")
    
    if not app_id and apps:
        app_id = apps[0].get_id
    
    if app_id:
        app = Application.get(app_id)
        case_short = app.modules[module_id].get_detail("case_short")
        case_long = app.modules[module_id].get_detail("case_long")
    else:
        case_short=""
        case_long=""
    
    return render_to_response(request, "cloudcare/list_cases.html", 
                              {"domain": domain,
                               "language": language,
                               "user_id": user_id,
                               "apps": apps,
                               "case_short": json.dumps(case_short._doc),
                               "case_long": json.dumps(case_long._doc),
                               "cases": json.dumps(get_owned_cases(domain, user_id),
                                                   default=json_handler)})


cloudcare_api = login_or_digest_ex(allow_cc_users=True)

@login_and_domain_required
def view_case(request, domain, case_id=None):
    context = {}
    case_json = CommCareCase.get(case_id).get_json() if case_id else None
    case_type = case_json['properties']['case_type'] if case_json else None
    case_spec_id = request.GET.get('spec')
    if case_spec_id:
        case_spec = CaseSpec.get(case_spec_id)
    else:
        case_spec = None
        context.update(dict(
            suggested_case_specs=CaseSpec.get_suggested(domain, case_type)
        ))
    context.update({
        'case': case_json,
        'domain': domain,
        'case_spec': case_spec
    })
    return render_to_response(request, 'cloudcare/view_case.html', context)

@cloudcare_api
def get_groups(request, domain, user_id):
    user = CouchUser.get_by_user_id(user_id, domain)
    groups = Group.by_user(user)
    return json_response(sorted([{'label': group.name, 'value': group.get_id} for group in groups], key=lambda x: x['label']))

@cloudcare_api
def get_cases(request, domain):

    if request.couch_user.is_commcare_user():
        user_id = request.couch_user.get_id
    else:
        user_id = request.REQUEST.get("user_id", "")

    if not user_id and not request.couch_user.is_web_user():
        return HttpResponseBadRequest("Must specify user_id!")

    @dict
    @inline
    def filters():
        """copy request.REQUEST but exclude user_id"""
        for path, val in request.REQUEST.items():
            if path != 'user_id':
                yield (path, val)

    cases = get_filtered_cases(domain, user_id=user_id, filters=filters)
    return json_response(cases)

@cloudcare_api
def filter_cases(request, domain, app_id, module_id):
    app = Application.get(app_id)
    module = app.get_module(module_id)
    auth_cookie = request.COOKIES.get('sessionid')
    details = module.details
    xpath_parts = []
    for detail in details:
        if detail.filter_xpath_2():
            xpath_parts.append(detail.filter_xpath_2())
    xpath = "".join(xpath_parts)
    # touchforms doesn't like this to be escaped
    xpath = HTMLParser.HTMLParser().unescape(xpath)
    additional_filters = {"properties/case_type": module.case_type }
    result = touchforms_api.filter_cases(domain, request.couch_user, 
                                         xpath, additional_filters, 
                                         auth=DjangoAuth(auth_cookie))
    case_ids = result.get("cases", [])
    cases = [CommCareCase.get(id) for id in case_ids]
    cases = [c.get_json() for c in cases if c]
    return json_response(cases)
    
@cloudcare_api
def get_apps_api(request, domain):
    return json_response(get_cloudcare_apps(domain))

@cloudcare_api
def get_app_api(request, domain, app_id):
    return json_response(get_app(domain, app_id))

@cloudcare_api
def get_fixtures(request, domain, user_id, fixture_id=None):
    user = CommCareUser.get_by_user_id(user_id)
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
        for fixture in generator.get_fixtures(casexml_user, version=V2):
            if fixture.attrib.get("id") == fixture_id:
                assert len(fixture.getchildren()) == 1
                return HttpResponse(ElementTree.tostring(fixture.getchildren()[0]), content_type="text/xml")
        raise Http404
        
        