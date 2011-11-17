from couchdbkit.ext.django.schema import *
from dimagi.utils.mixins import UnicodeMixIn
from casexml.apps.case import const

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
    previous_log_id = StringProperty()  # previous sync log, forming a chain
    last_seq = IntegerProperty()        # the last_seq of couch during this sync
    cases = StringListProperty()
    
    purged_cases = StringListProperty() # cases that were purged during this sync. 
    
    # cases that were submitted between this sync and the next one
    # broken down by how they were modified (note that cases can,
    # and often will, appear in more than one of these lists)
    # (these are stored redundantly, but avoid excessive cross lookups at sync-time)
    created_cases = StringListProperty() 
    updated_cases = StringListProperty() 
    closed_cases = StringListProperty() 
    submitted_forms = StringListProperty()
    
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
        if not hasattr(self, "_previous_log_ref"):
            self._previous_log_ref = SyncLog.get(self.previous_log_id) if self.previous_log_id else None
        return self._previous_log_ref
    
    def _walk_the_chain(self, func):
        """
        Given a function that takes in a log and returns a list, 
        walk up the chain to extend the list by calling the function
        on all parents.
        
        Returns a set object, stripping all duplicate ids
        
        Used to generate case id lists for synced, purged, and other cases
        """
        chain = set(func(self))
        previous_log = self.get_previous_log()
        if previous_log:
            chain = chain | previous_log._walk_the_chain(func)
        return chain
        
    
    def get_synced_case_ids(self):
        """
        All cases that have been touched, either by this or
        any previous syncs that this knew about.
        """
        if not hasattr(self, "_touched_case_ids"):
            self._touched_case_ids = self._walk_the_chain\
                (lambda synclog: [id for id in synclog.cases])
        return self._touched_case_ids
    
    def get_purged_case_ids(self):
        """
        All cases that have been purged, either by this or
        any previous syncs that this knew about.
        """
        if not hasattr(self, "_purged_case_ids"):
            self._purged_case_ids = self._walk_the_chain\
                (lambda synclog: [id for id in synclog.purged_cases])
        return self._purged_case_ids
    
    def get_created_case_ids(self):
        # TODO: cache if necessary
        return self._walk_the_chain\
                (lambda synclog: [id for id in synclog.created_cases])
    
    def get_updated_case_ids(self):
        # TODO: cache if necessary
        return self._walk_the_chain\
                (lambda synclog: [id for id in synclog.updated_cases])
    
    def get_closed_case_ids(self):
        # TODO: cache if necessary
        return self._walk_the_chain\
                (lambda synclog: [id for id in synclog.closed_cases])
    
    def get_submitted_case_ids(self):
        # TODO: cache if necessary
        ret = self.get_created_case_ids()
        ret = ret | self.get_updated_case_ids()
        ret = ret | self.get_closed_case_ids()
        return ret
        
    def get_submitted_form_ids(self):
        # TODO: cache if necessary
        return self._walk_the_chain\
                (lambda synclog: [id for id in synclog.submitted_forms])
        
    def get_all_cases_seen(self):
        """
        All cases the phone has ever seen.
        Union of:
         - any case previously synced.
         - any case that has ever been submitted to.
        """
        ret = self.get_synced_case_ids()
        ret = ret | self.get_submitted_case_ids()
        return ret
    
    def get_open_cases_on_phone(self):
        """
        The current list of open cases on the phone.
        The formula is:
         - Cases synced down PLUS cases submitted by phone 
           MINUS (cases closed by phone PLUS cases already purged) 
        """
        ret = self.get_all_cases_seen() 
        # TODO: Asserts? Anything in the latter two sets
        # should have already been in the original list
        ret = ret - self.get_closed_case_ids()
        ret = ret - self.get_purged_case_ids()
        return ret
    
    def update_submitted_lists(self, xform, case_list):
        # for all the cases update the relevant lists in the sync log
        # so that we can build a historical record of what's associated
        # with the phone
        if xform.get_id not in self.submitted_forms:
            self.submitted_forms.append(xform.get_id)
        for case in case_list:
            actions = case.get_actions_for_form(xform.get_id)
            for action in actions:
                if action.action_type == const.CASE_ACTION_CREATE \
                   and case.get_id not in self.created_cases:
                    self.created_cases.append(case.get_id)
                elif action.action_type == const.CASE_ACTION_UPDATE \
                   and case.get_id not in self.updated_cases:
                    self.updated_cases.append(case.get_id)
           
                elif action.action_type == const.CASE_ACTION_CLOSE \
                   and case.get_id not in self.closed_cases:
                    self.closed_cases.append(case.get_id)
        self.save()
            
    def __unicode__(self):
        return "%s synced on %s (%s)" % (self.chw_id, self.date.date(), self.get_id)

from casexml.apps.phone import signals