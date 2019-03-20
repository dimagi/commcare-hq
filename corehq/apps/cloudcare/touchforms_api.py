from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.users.models import CouchUser
from corehq.util.python_compatibility import soft_assert_type_text
import six

DELEGATION_STUB_CASE_TYPE = "cc_delegation_stub"


class BaseSessionDataHelper(object):

    def __init__(self, domain, couch_user):
        self.domain = domain
        self.couch_user = couch_user

    def get_session_data(self, device_id=CLOUDCARE_DEVICE_ID):
        """
        Get session data used by touchforms.
        """
        session_data = {
            'device_id': device_id,
            'app_version': '2.0',
            'domain': self.domain,
        }
        session_data.update(get_user_contributions_to_touchforms_session(self.couch_user))
        return session_data

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
        xform_url = root_extras.get('formplayer_url')
        ret = {
            "session_data": session_data,
            "xform_url": xform_url,
        }
        ret.update(root_extras)
        return ret


class CaseSessionDataHelper(BaseSessionDataHelper):

    def __init__(self, domain, couch_user, case_id_or_case, app, form, delegation=False):
        super(CaseSessionDataHelper, self).__init__(domain, couch_user)
        self.form = form
        self.app = app
        if case_id_or_case is None or isinstance(case_id_or_case, six.string_types):
            if case_id_or_case is not None:
                soft_assert_type_text(case_id_or_case)
            self.case_id = case_id_or_case
            self._case = None
        else:
            self.case_id = case_id_or_case.case_id
            self._case = case_id_or_case
        self._delegation = delegation

    @property
    def case(self):
        if not self._case:
            self._case = CaseAccessors(self.domain).get_case(self.case_id)
        return self._case

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
        session_data = super(CaseSessionDataHelper, self).get_session_data(device_id)
        if self.case_id:
            if self.delegation:
                session_data["delegation_id"] = self.case_id
                session_data["case_id"] = self._case_parent_id
            else:
                session_data[self.case_session_variable_name] = self.case_id
        if self.app:
            session_data["app_id"] = self.app.get_id
        return session_data

    @property
    def case_session_variable_name(self):
        session_var = 'case_id'
        datums = EntriesHelper(self.app).get_datums_meta_for_form_generic(self.form)
        datums = [datum for datum in datums if datum.case_type == self.case_type]
        if len(datums) == 1:
            session_var = datums[0].datum.id
        return session_var


def get_user_contributions_to_touchforms_session(couch_user_or_commconnect_case):
    return {
        'username': couch_user_or_commconnect_case.raw_username,
        'user_id': couch_user_or_commconnect_case.get_id,
        # This API is used by smsforms, so sometimes "couch_user" can be
        # a case, in which case there is no user_data.
        'user_data': (couch_user_or_commconnect_case.user_session_data
            if isinstance(couch_user_or_commconnect_case, CouchUser) else {}),
    }
