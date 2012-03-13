from casexml.apps.case.models import CommCareCase
from corehq.apps.cloudcare.models import CaseSpec
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser
from dimagi.utils.web import render_to_response, json_response, json_handler
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from corehq.apps.app_manager.models import Application, ApplicationBase
import json
from corehq.apps.cloudcare.api import get_owned_cases, get_app, get_apps
from touchforms.formplayer.models import PlaySession
from dimagi.utils.couch import safe_index

@login_and_domain_required
def app_list(request, domain):
    apps = get_apps(domain)
    language = request.REQUEST.get("language", "en")
    return render_to_response(request, "cloudcare/list_apps.html", 
                              {"domain": domain,
                               "language": language,
                               "apps": json.dumps(apps)})

@login_and_domain_required
def view_app(request, domain, app_id):
    # TODO
    return HttpResponse("fixme")

@login_and_domain_required
def enter_form(request, domain, app_id, module_id, form_id):
    app = Application.get(app_id)
    module = app.get_module(module_id)
    form = module.get_form(form_id)
    preloader_data = {"meta": {"UserID":   request.couch_user.get_id,
                               "UserName":  request.user.username},
                      "property": {"deviceID": "cloudcare"}}
    # check for a case id and update preloader appropriately
    case_id = request.REQUEST.get("case_id")
    if case_id:
        case = CommCareCase.get(case_id)
        preloader_data["case"] = case.get_preloader_dict()
    
    return render_to_response(request, "cloudcare/play_form.html",
                              {"domain": domain, 
                               "form": form, 
                               "preloader_data": json.dumps(preloader_data),
                               "app_id": app_id, 
                               "module_id": module_id,
                               "form_id": form_id})

@login_and_domain_required
def form_complete(request, domain, app_id, module_id, form_id):
    app = Application.get(app_id)
    module = app.get_module(module_id)
    form = module.get_form(form_id)
    session_id = request.REQUEST.get("session_id")
    session = PlaySession.get(session_id) if session_id else None
    return render_to_response(request, "cloudcare/form_complete.html",
                              {"domain": domain, 
                               "session": session, 
                               "app_id": app_id, 
                               "module_id": module_id,
                               "form_id": form_id})


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

cloudcare_api = login_and_domain_required

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
    cases = get_owned_cases(domain, request.couch_user.get_id)
    if request.REQUEST:
        def _filter(case):
            for path, val in request.REQUEST.items():
                if safe_index(case, path.split("/")) != val:
                    return False
            return True
        cases = filter(_filter, cases)
        
    return json_response(cases)

@cloudcare_api
def get_apps_api(request, domain):
    return json_response(get_apps(domain))

@cloudcare_api
def get_app_api(request, domain, app_id):
    return json_response(get_app(domain, app_id))
