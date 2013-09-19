import warnings
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.case.exceptions import BadStateException, RestoreException
from casexml.apps.phone.models import SyncLog, CaseState
import logging
from dimagi.utils.couch.database import get_db, get_safe_write_kwargs
from casexml.apps.phone import xml
from datetime import datetime
from receiver.xml import get_response_element, get_simple_response_xml,\
    ResponseNature
from casexml.apps.case.xml import check_version, V1
from casexml.apps.phone.fixtures import generator
from django.http import HttpResponse
from casexml.apps.phone.checksum import CaseStateHash


class RestoreConfig(object):
    """
    A collection of attributes associated with an OTA restore
    """
    def __init__(self, user, restore_id="", version=V1, state_hash="", caching_enabled=False):
        self.user = user
        self.restore_id = restore_id
        self.version = version
        self.state_hash = state_hash
        self.caching_enabled = caching_enabled

    @property
    @memoized
    def sync_log(self):
        return SyncLog.get(self.restore_id) if self.restore_id else None


    def validate(self):
        # runs validation checks, raises exceptions if anything is amiss
        check_version(self.version)
        if self.sync_log and self.state_hash:
            parsed_hash = CaseStateHash.parse(self.state_hash)
            if self.sync_log.get_state_hash() != parsed_hash:
                raise BadStateException(expected=self.sync_log.get_state_hash(),
                                        actual=parsed_hash,
                                        case_ids=self.sync_log.get_footprint_of_cases_on_phone())


    def get_payload(self):
        user = self.user
        last_sync = self.sync_log

        self.validate()

        if self.caching_enabled and self.sync_log and self.sync_log.get_cached_payload(self.version):
            return self.sync_log.get_cached_payload(self.version)

        sync_operation = user.get_case_updates(last_sync)
        case_xml_elements = [xml.get_case_element(op.case, op.required_updates, self.version)
                             for op in sync_operation.actual_cases_to_sync]


        last_seq = str(get_db().info()["update_seq"])

        # create a sync log for this
        previous_log_id = last_sync.get_id if last_sync else None

        synclog = SyncLog(user_id=user.user_id, last_seq=last_seq,
                          owner_ids_on_phone=user.get_owner_ids(),
                          date=datetime.utcnow(), previous_log_id=previous_log_id,
                          cases_on_phone=[CaseState.from_case(c) for c in \
                                          sync_operation.actual_owned_cases],
                          dependent_cases_on_phone=[CaseState.from_case(c) for c in \
                                                    sync_operation.actual_extended_cases])
        synclog.save(**get_safe_write_kwargs())

        # start with standard response
        response = get_response_element(
            "Successfully restored account %s!" % user.username,
            ResponseNature.OTA_RESTORE_SUCCESS)

        # add sync token info
        response.append(xml.get_sync_element(synclog.get_id))
        # registration block
        response.append(xml.get_registration_element(user))
        # fixture block
        for fixture in generator.get_fixtures(user, self.version, last_sync):
            response.append(fixture)
        # case blocks
        for case_elem in case_xml_elements:
            response.append(case_elem)

        resp = xml.tostring(response)
        if self.caching_enabled:
            self.sync_log.set_cached_payload(resp, self.version)
        return resp

    def get_response(self):
        try:
            return HttpResponse(self.get_payload(), mimetype="text/xml")
        except RestoreException, e:
            logging.exception("%s error during restore submitted by %s: %s" %
                              (type(e).__name__, self.user.username, str(e)))
            response = get_simple_response_xml(
                e.message,
                ResponseNature.OTA_RESTORE_ERROR
            )
            return HttpResponse(response, mimetype="text/xml",
                                status=412)  # precondition failed


def generate_restore_payload(user, restore_id="", version=V1, state_hash=""):
    """
    Gets an XML payload suitable for OTA restore. If you need to do something
    other than find all cases matching user_id = user.user_id then you have
    to pass in a user object that overrides the get_case_updates() method.
    
    It should match the same signature as models.user.get_case_updates():
    
        user:          who the payload is for. must implement get_case_updates
        restore_id:    sync token
        version:       the CommCare version 
        
        returns: the xml payload of the sync operation
    """
    warnings.warn("generate_restore_payload is deprecated. use RestoreConfig", DeprecationWarning)
    config = RestoreConfig(user, restore_id, version, state_hash)
    return config.get_payload()

def generate_restore_response(user, restore_id="", version="1.0", state_hash=""):
    warnings.warn("generate_restore_payload is deprecated. use RestoreConfig", DeprecationWarning)
    return RestoreConfig(user, restore_id, version, state_hash).get_response()
