from datetime import date
from couchdbkit.ext.django.schema import *
import logging
from casexml.apps.case import const
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

from corehq.apps.phone import signals