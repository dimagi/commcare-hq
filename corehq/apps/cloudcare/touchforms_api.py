from touchforms.formplayer.api import post_data
import json
from django.conf import settings
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.app_manager.const import APP_V2, APP_V1
from casexml.apps.case.models import CommCareCase
from django.core.urlresolvers import reverse


def get_session_data(domain, couch_user, case_id=None, version=APP_V2, 
                     device_id=CLOUDCARE_DEVICE_ID):
    """
    Get session data used by touchforms.
    """
    # expected properties: .raw_username, .get_id
    if version == APP_V2:
        session_data = {'device_id': device_id,
                        'app_version': '2.0',
                        'username': couch_user.raw_username,
                        'user_id': couch_user.get_id,
                        "domain": domain
                        }
        if case_id:
            session_data["case_id"] = case_id
    else:
        assert version == APP_V1
        # assume V1 / preloader structure
        session_data = {"meta": {"UserID":    couch_user.get_id,
                                 "UserName":  couch_user.raw_username},
                        "property": {"deviceID": CLOUDCARE_DEVICE_ID}}
        # check for a case id and update preloader appropriately
        if case_id:
            case = CommCareCase.get(case_id)
            session_data["case"] = case.get_preloader_dict()
    
    return session_data

def filter_cases(domain, couch_user, xpath, additional_filters={}, auth=None):
    """
    Filter a list of cases by an xpath expression + additional filters
    """
    data = {"action": "touchcare-filter-cases",
            "filter_expr": xpath }
    data["session_data"] = get_session_data(domain, couch_user)
    data["session_data"]["additional_filters"] = additional_filters
    response = post_data(json.dumps(data), url=settings.XFORMS_PLAYER_URL,
                         content_type="text/json", auth=auth)
    return json.loads(response)

def get_full_context(domain, user, app, module, form, case_id=None):
    """
    Get the entire touchforms context for a given user/app/module/form/case
    """
    session_data = get_session_data(domain, user, case_id, 
                                    app.application_version)
    return {"form_content": form.render_xform(),
            "session_data": session_data, 
            "xform_url": reverse("xform_player_proxy")}

    