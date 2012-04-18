from touchforms.formplayer.api import post_data
import json
from django.conf import settings
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID


def get_session_data(domain, couch_user):
    """
    Get session data used by touchforms
    """
    return { 'device_id': CLOUDCARE_DEVICE_ID,
             'app_version': '2.0',
             'username': couch_user.raw_username,
             'user_id': couch_user.get_id,
             "domain": domain
            }

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
