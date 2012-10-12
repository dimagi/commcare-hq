from casexml.apps.case.models import CommCareCase
from dimagi.utils.decorators.memoized import memoized
from touchforms.formplayer.api import post_data
import json
from django.conf import settings
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from django.core.urlresolvers import reverse

DELEGATION_STUB_CASE_TYPE = "cc_delegation_stub"

class SessionDataHelper(object):
    def __init__(self, domain, couch_user, case_id=None):
        self.domain = domain
        self.couch_user = couch_user
        self.case_id = case_id

    @property
    @memoized
    def case(self):
        return CommCareCase.get(self.case_id)

    @property
    def case_type(self):
        return self.case.type

    @property
    def case_parent_id(self):
        return self.case.get_index_map()['parent']

    @property
    def delegation_mode(self):
        return self.case_type == DELEGATION_STUB_CASE_TYPE

    def get_session_data(self, device_id=CLOUDCARE_DEVICE_ID):
        """
        Get session data used by touchforms.
        """

        session_data = {
            'device_id': device_id,
            'app_version': '2.0',
            'username': self.couch_user.raw_username,
            'user_id': self.couch_user.get_id,
            "domain": self.domain,
        }
        if self.case_id:
            if self.delegation_mode:
                session_data["delegation_id"] = self.case_id
                session_data["case_id"] = self.case_parent_id
            else:
                session_data["case_id"] = self.case_id

        return session_data

    def filter_cases(self, xpath, additional_filters=None, auth=None):
        """
        Filter a list of cases by an xpath expression + additional filters
        """
        session_data = self.get_session_data()
        session_data["additional_filters"] = additional_filters or {}

        data = {
            "action": "touchcare-filter-cases",
            "filter_expr": xpath,
            "session_data": session_data,
        }

        response = post_data(
            json.dumps(data),
            url=settings.XFORMS_PLAYER_URL,
            content_type="text/json", auth=auth
        )

        return json.loads(response)

    def get_full_context(self, form):
        """
        Get the entire touchforms context for a given user/app/module/form/case
        """
        session_data = self.get_session_data()
        # always tell touchforms to include footprinted cases in it's case db
        session_data["additional_filters"] = {"footprint": True}
        return {
            "form_content": form.render_xform(),
            "session_data": session_data,
            "xform_url": reverse("xform_player_proxy")
        }



def get_session_data(domain, couch_user, case_id=None, device_id=CLOUDCARE_DEVICE_ID):
    return SessionDataHelper(domain, couch_user, case_id).get_session_data(device_id)

def filter_cases(domain, couch_user, xpath, additional_filters=None, auth=None):
    return SessionDataHelper(domain, couch_user).filter_cases(xpath, additional_filters, auth)

def get_full_context(domain, user, app, module, form, case_id=None):
    return SessionDataHelper(domain, user, case_id).get_full_context(form)