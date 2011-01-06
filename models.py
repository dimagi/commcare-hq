from datetime import date
from couchdbkit.ext.django.schema import *
import logging
from corehq.apps.case import const
from couchforms.safe_index import safe_index
import hashlib
from dimagi.utils.mixins import UnicodeMixIn

class SyncLog(Document, UnicodeMixIn):
    """
    A log of a single sync operation.
    """
    
    date = DateTimeProperty()
    user_id = StringProperty()
    previous_log_id = StringProperty() # previous sync log, forming a chain
    last_seq = IntegerProperty() # the last_seq of couch during this sync
    cases = StringListProperty()
    
    @classmethod
    def last_for_chw(cls, chw_id):
        return SyncLog.view("phone/sync_logs_by_chw", 
                            startkey=[chw_id, {}],
                            endkey=[chw_id, ""],
                            descending=True,
                            limit=1,
                            reduce=False,
                            include_docs=True).one()

    def get_previous_log(self):
        """
        Get the previous sync log, if there was one.  Otherwise returns nothing.
        """
        if self.previous_log_id:    
            return SyncLog.get(self.previous_log_id)
        return None
    
    def get_synced_case_ids(self):
        """
        All cases that have been touched, either by this or
        any previous syncs that this knew about.
        """
        if not hasattr(self, "_touched_case_ids"):
            cases = [case for case in self.cases]
            previous_log = self.get_previous_log()
            if previous_log:
                cases.extend(previous_log.get_synced_case_ids())
            # remove duplicates
            self._touched_case_ids = list(set(cases))
        return self._touched_case_ids
    
    def __unicode__(self):
        return "%s synced on %s (%s)" % (self.chw_id, self.date.date(), self.get_id)

class PhoneCase(Document, UnicodeMixIn):
    """
    Case objects that go to phones. 
    """
    
    case_id = StringProperty()
    date_modified = DateTimeProperty()
    case_type_id = StringProperty()
    user_id = StringProperty()
    case_name = StringProperty()
    external_id = StringProperty()
    
    activation_date = DateProperty() # (don't followup before this date) 
    due_date = DateProperty() # (followup by this date)
    missed_appt_date = DateProperty()
    
    # system properties
    start_date = DateProperty()
    
    def __unicode__(self):
        return self.get_unique_string()
    
    def is_started(self, since=None):
        """
        Whether the case has started (since a date, or today).
        """
        if since is None:
            since = date.today()
        return self.start_date <= since if self.start_date else True
    
    
    def get_unique_string(self):
        """
        A unique identifier for this based on some of its contents
        """
        # in theory since case ids are unique and modification dates get updated
        # upon any change, this is all we need
        return "%(case_id)s::%(date_modified)s::%(user_id)s::%(external_id)s::%(start_date)s" % \
                {"case_id": self.case_id, "date_modified": self.date_modified,
                 "user_id": self.user_id, "external_id": self.external_id,
                 "start_date": self.start_date}
    
    def _get_id(self):
        return hashlib.sha1(self.get_unique_string()).hexdigest()
        
    def save(self, *args, **kwargs):
        # override save to make this read-only, use a generated id,
        # and not re-save objects that have already been saved
        if self._id:
            raise Exception("Sorry this model is read only and the ID must be "
                            "automatically generated!")
        
        id = self._get_id()
        if PhoneCase.get_db().doc_exist(id):
            # we assume we don't need to recreate this, since it's the same
            # exact object
            pass
        else:
            self._id = id
            super(PhoneCase, self).save(*args, **kwargs)
    
    
    @classmethod
    def from_bhoma_case(cls, case):
        if not case.patient:
            logging.error("No patient found found inside %s, will not be downloaded to phone" % case)
            return None
        
        # complicated logic, but basically a case is open based on the conditions 
        # below which amount to it not being closed, and if it has a start date, 
        # that start date being before or up to today
        open_inner_cases = [cinner for cinner in case.commcare_cases if not cinner.closed]
                               
        if len(open_inner_cases) == 0:
            logging.warning("No open case found inside %s, will not be downloaded to phone" % case)
            return None
        elif len(open_inner_cases) > 1:
            logging.error("More than one open case found inside %s.  Only the most recent will not be downloaded to phone" % case)
            ccase = sorted(open_inner_cases, key=lambda case: case.opened_on)[0]
        else:
            ccase = open_inner_cases[0]
        return PhoneCase(**{"case_id": ccase._id,
                            "date_modified": case.modified_on,
                            "case_type_id": const.CASE_TYPE_BHOMA_FOLLOWUP,
                            "user_id": ccase.user_id,
                            "case_name": ccase.name,
                            "external_id": ccase.external_id,
                            "activation_date": ccase.activation_date, 
                            "due_date": ccase.due_date, 
                            
                            "missed_appt_date": safe_index(ccase, ["missed_appointment_date",]),
                            "start_date": ccase.start_date
                            })

from corehq.apps.phone import signals