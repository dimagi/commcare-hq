from casexml.apps.case.models import CommCareCase
from dimagi.utils.decorators.memoized import memoized
from touchforms.formplayer.api import post_data
import json
from django.conf import settings
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from django.core.urlresolvers import reverse
from corehq.apps.users.models import CommCareUser

DELEGATION_STUB_CASE_TYPE = "cc_delegation_stub"

class SessionDataHelper(object):
    def __init__(self, domain, couch_user, case_id=None, delegation=False, offline=False):
        self.domain = domain
        self.couch_user = couch_user
        self.case_id = case_id
        self._delegation = delegation
        self.offline = offline

    @property
    @memoized
    def case(self):
        return CommCareCase.get(self.case_id)

    @property
    def case_type(self):
        return self.case.type

    @property
    def _case_parent_id(self):
        """Only makes sense if the case is a delegation stub"""
        return self.case.get_index_map().get('parent')['case_id']

    @property
    def delegation(self):
        if self._delegation and self.case_id:
            assert self.case_type == DELEGATION_STUB_CASE_TYPE
        return self._delegation


    def get_session_data(self, device_id=CLOUDCARE_DEVICE_ID):
        """
        Get session data used by touchforms.
        """
        # NOTE: Better to use isinstance(self.couch_user, CommCareUser) here rather than 
        # self.couch_user.is_commcare_user() since this function is reused by smsforms where
        # the recipient can be a case.
        session_data = {
            'device_id': device_id,
            'app_version': '2.0',
            'username': self.couch_user.raw_username,
            'user_id': self.couch_user.get_id,
            'domain': self.domain,
            'user_data': self.couch_user.user_data if isinstance(self.couch_user, CommCareUser) else {},
        }
        if self.case_id:
            if self.delegation:
                session_data["delegation_id"] = self.case_id
                session_data["case_id"] = self._case_parent_id
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

    def get_full_context(self, root_extras=None, session_extras=None):
        """
        Get the entire touchforms context for a given user/app/module/form/case
        """
        root_extras = root_extras or {}
        session_extras = session_extras or {}
        session_data = self.get_session_data()
        # always tell touchforms to include footprinted cases in its case db
        session_data["additional_filters"] = {"footprint": True}
        session_data.update(session_extras)
        online_url = reverse("xform_player_proxy")
        offline_url = 'http://localhost:%d' % settings.OFFLINE_TOUCHFORMS_PORT
        ret = {
            "session_data": session_data,
            "xform_url": offline_url if self.offline else online_url,
        }
        ret.update(root_extras)
        return ret


def get_session_data(domain, couch_user, case_id=None, device_id=CLOUDCARE_DEVICE_ID, delegation=False):
    return SessionDataHelper(domain, couch_user, case_id, delegation=delegation).get_session_data(device_id)

def filter_cases(domain, couch_user, xpath, additional_filters=None, auth=None, delegation=False):
    return SessionDataHelper(domain, couch_user, delegation=delegation).filter_cases(xpath, additional_filters, auth)
