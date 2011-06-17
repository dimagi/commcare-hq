from couchdbkit.ext.django.schema import *
from dimagi.utils.mixins import UnicodeMixIn

class User(object):
    """
    This is a basic user model that's used for OTA restore to properly
    find cases and generate the user XML.
    """
    
    def __init__(self, user_id, username, password, date_joined, user_data={}):
        self.user_id = user_id
        self.username = username
        self.password = password
        self.date_joined = date_joined
        self.user_data = user_data
    
    def get_open_cases(self, last_sync):
        """
        Get open cases associated with the user. This method
        can be overridden to change case-syncing behavior
        
        returns: list of (CommCareCase, previously_synced) tuples
        """
        from casexml.apps.phone.caselogic import get_open_cases_to_send
        return get_open_cases_to_send(self, last_sync)
    
    @classmethod
    def from_django_user(cls, django_user):
        return cls(user_id=str(django_user.pk), username=django_user.username,
                   password=django_user.password, date_joined=django_user.date_joined,
                   user_data={})
    
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
    def last_for_user(cls, user_id):
        return SyncLog.view("phone/sync_logs_by_user", 
                            startkey=[user_id, {}],
                            endkey=[user_id, ""],
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

from casexml.apps.phone import signals