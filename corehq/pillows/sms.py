from corehq.apps.reminders.models import CaseReminder
from corehq.apps.sms.models import SMSLog, WORKFLOW_REMINDER
from corehq.pillows.mappings.sms_mapping import SMS_MAPPING, SMS_INDEX
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import AliasedElasticPillow
from django.conf import settings

CUSTOM_DOMAINS = [k for k, v in settings.DOMAIN_MODULE_MAP.items() if v == 'custom.trialconnect']
TC_STUB = 'tc__'  # stub to user for prepending key names in elasticsearch docs for fields needed for trialconnect

class SMSPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = SMSLog   # while this index includes all users,
                                    # I assume we don't care about querying on properties specfic to WebUsers
    couch_filter = "sms/all_logs"
    es_host = settings.ELASTICSEARCH_HOST
    es_port = settings.ELASTICSEARCH_PORT
    es_timeout = 60
    es_index_prefix = "smslogs"
    es_alias = "smslogs"
    es_type = "sms"
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                }
            }
        }
    }
    es_index = SMS_INDEX
    default_mapping = SMS_MAPPING

    @memoized
    def calc_meta(self):
        #todo: actually do this correctly

        """
        override of the meta calculator since we're separating out all the types,
        so we just do a hash of the "prototype" instead to determined md5
        """
        return self.calc_mapping_hash({"es_meta": self.es_meta,
                                       "mapping": self.default_mapping})

    def get_mapping_from_type(self, doc_dict):
        """
        Define mapping uniquely to the user_type document.
        See below on why date_detection is False

        NOTE: DO NOT MODIFY THIS UNLESS ABSOLUTELY NECESSARY. A CHANGE BELOW WILL GENERATE A NEW
        HASH FOR THE INDEX NAME REQUIRING A REINDEX+RE-ALIAS. THIS IS A SERIOUSLY RESOURCE
        INTENSIVE OPERATION THAT REQUIRES SOME CAREFUL LOGISTICS TO MIGRATE
        """
        #the meta here is defined for when the case index + type is created for the FIRST time
        #subsequent data added to it will be added automatically, but date_detection is necessary
        # to be false to prevent indexes from not being created due to the way we store dates
        #all are strings EXCEPT the core case properties which we need to explicitly define below.
        #that way date sort and ranges will work with canonical date formats for queries.
        return {
            self.get_type_string(doc_dict): self.default_mapping
        }

    def get_type_string(self, doc_dict):
        return self.es_type

    def needs_custom_transform(self, doc_dict):
        return doc_dict.get("workflow") == WORKFLOW_REMINDER and doc_dict["domain"] in CUSTOM_DOMAINS

    def add_case_data(self, doc_dict):
        reminder_id = doc_dict.get("reminder_id")
        reminder = get_db().get(reminder_id) if reminder_id else {}
        case_id = reminder.get('case_id')
        case = get_db().get(case_id) if case_id else {}
        doc_dict[TC_STUB + 'case_data'] = {
            "case_id": case_id,
            "case_type": case.get("case_type"),
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
            "case_type": case.get("case_type"),
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


