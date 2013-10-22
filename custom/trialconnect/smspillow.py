from corehq.apps.sms.models import WORKFLOW_REMINDER
from corehq.pillows.mappings.tc_sms_mapping import TCSMS_INDEX, TCSMS_MAPPING
from corehq.pillows.sms import SMSPillow
from dimagi.utils.couch.database import get_db

TC_STUB = 'tc__'  # stub to user for prepending key names in elasticsearch docs for fields needed for trialconnect

class TCSMSPillow(SMSPillow):
    """
    Simple/Common Case properties Indexer
    """

    couch_filter = "trialconnect/smslogs"
    es_index_prefix = "tc_smslogs"
    es_alias = "tc_smslogs"
    es_type = "tc_sms"
    es_index = TCSMS_INDEX
    default_mapping = TCSMS_MAPPING


    def needs_custom_transform(self, doc_dict):
        return doc_dict.get("workflow") == WORKFLOW_REMINDER

    def add_case_data(self, doc_dict):
        reminder_id = doc_dict.get("reminder_id")
        reminder = get_db().get(reminder_id) if reminder_id else {}
        case_id = reminder.get('case_id')
        case = get_db().get(case_id) if case_id else {}
        doc_dict[TC_STUB + 'case_data'] = {
            "case_id": case_id,
            "case_type": case.get("type"),
            "response_state": case.get("response_state") # todo: need to get response_state at time of sms log
        }
        return doc_dict

    def add_session_data(self, doc_dict):
        session_id = doc_dict.get('xforms_session_couch_id')
        session = get_db().get(session_id) if session_id else {}
        reminder_id = session.get("reminder_id")
        reminder = get_db().get(reminder_id) if reminder_id else {}
        case_id = reminder.get('case_id')
        case = get_db().get(case_id) if case_id else {}
        xform_id = session.get('submission_id')
        doc_dict[TC_STUB + 'session_data'] = {
            "session_id": session_id,
            "case_type": case.get("type"),
            "response_state": get_db().get(xform_id).get('_form', {}).get('response_state') if xform_id else None
        }
        return doc_dict

    def change_transform(self, doc_dict):
        doc_dict = super(SMSPillow, self).change_transform(doc_dict)
        if not self.needs_custom_transform(doc_dict):
            return doc_dict
        doc_dict = self.add_case_data(doc_dict)
        doc_dict = self.add_session_data(doc_dict)
        return doc_dict
