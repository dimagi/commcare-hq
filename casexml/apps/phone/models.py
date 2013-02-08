from couchdbkit.ext.django.schema import *
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch import LooselyEqualDocumentSchema
from casexml.apps.case import const
from casexml.apps.case.sharedmodels import CommCareCaseIndex, IndexHoldingMixIn
from casexml.apps.phone.checksum import Checksum, CaseStateHash
import logging


class User(object):
    """ 
    This is a basic user model that's used for OTA restore to properly
    find cases and generate the user XML.
    """
    
    def __init__(self, user_id, username, password, date_joined, 
                 user_data=None, additional_owner_ids=[]):
        self.user_id = user_id
        self.username = username
        self.password = password
        self.date_joined = date_joined
        self.user_data = user_data or {}
        self.additional_owner_ids = additional_owner_ids
    
    def get_owner_ids(self):
        ret = [self.user_id]
        ret.extend(self.additional_owner_ids)
        return list(set(ret))
        
    def get_case_updates(self, last_sync):
        """
        Get open cases associated with the user. This method
        can be overridden to change case-syncing behavior
        
        returns: A CaseSyncOperation object
        """
        from casexml.apps.phone.caselogic import get_case_updates
        return get_case_updates(self, last_sync)
    
    @classmethod
    def from_django_user(cls, django_user):
        return cls(user_id=str(django_user.pk), username=django_user.username,
                   password=django_user.password, date_joined=django_user.date_joined,
                   user_data={})
    

class CaseState(LooselyEqualDocumentSchema, IndexHoldingMixIn):
    """
    Represents the state of a case on a phone.
    """
    
    case_id = StringProperty()
    indices = SchemaListProperty(CommCareCaseIndex)
    
    @classmethod
    def from_case(cls, case):
        return cls(case_id=case.get_id,
                         indices=case.indices)

class ConfigurableAssertionMixin(object):
    """
    Provides a ._assert() function that can be configured using a class-level
    flag called 'strict'
    """
    strict = True

    def _assert(self, conditional, msg=""):
        if self.strict:
            assert conditional, msg
        elif not conditional:
            logging.warn("assertion failed: %s" % msg)
            self.has_assert_errors = True

class SyncLog(Document, UnicodeMixIn, ConfigurableAssertionMixin):
    """
    A log of a single sync operation.
    """
    
    date = DateTimeProperty()
    user_id = StringProperty()
    previous_log_id = StringProperty()  # previous sync log, forming a chain
    last_seq = IntegerProperty()        # the last_seq of couch during this sync
    
    # we need to store a mapping of cases to indices for generating the footprint

    # The cases_on_phone property represents the state of all cases the server thinks
    # the phone has on it and cares about.


    # The dependant_cases_on_phone property represents the possible list of cases
    # also on the phone because they are referenced by a real case's index (or 
    # a dependent case's index). This list is not necessarily a perfect reflection
    # of what's on the phone, but is guaranteed to be after pruning
    cases_on_phone = SchemaListProperty(CaseState)
    dependent_cases_on_phone = SchemaListProperty(CaseState)

    # The owner ids property keeps track of what ids the phone thinks it's the owner
    # of. This typically includes the user id, as well as all groups that that user
    # is a member of.
    owner_ids_on_phone = StringListProperty()

    @classmethod
    def wrap(cls, data):
        ret = super(SyncLog, cls).wrap(data)
        if hasattr(ret, 'has_assert_errors'):
            ret.strict = False
        return ret

    @classmethod
    def last_for_user(cls, user_id):
        return SyncLog.view("phone/sync_logs_by_user", 
                            startkey=[user_id, {}],
                            endkey=[user_id],
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
    
    def phone_has_case(self, case_id):
        """
        Whether the phone currently has a case, according to this sync log
        """
        return self.get_case_state(case_id) is not None
        
    def get_case_state(self, case_id):
        """
        Get the case state object associated with an id, or None if no such
        object is found
        """
        filtered_list = [case for case in self.cases_on_phone if case.case_id == case_id]
        if filtered_list:
            self._assert(len(filtered_list) == 1, \
                         "Should be exactly 0 or 1 cases on phone but were %s for %s" % \
                         (len(filtered_list), case_id))
            return filtered_list[0]
        return None
    
    def phone_has_dependent_case(self, case_id):
        """
        Whether the phone currently has a dependent case, according to this sync log
        """
        return self.get_dependent_case_state(case_id) is not None
        
    def get_dependent_case_state(self, case_id):
        """
        Get the dependent case state object associated with an id, or None if no such
        object is found
        """
        filtered_list = [case for case in self.dependent_cases_on_phone if case.case_id == case_id]
        if filtered_list:
            self._assert(len(filtered_list) == 1, \
                         "Should be exactly 0 or 1 dependent cases on phone but were %s for %s" % \
                         (len(filtered_list), case_id))
            return filtered_list[0]
        return None
    
    def _get_case_state_from_anywhere(self, case_id):
        return self.get_case_state(case_id) or self.get_dependent_case_state(case_id)
    
    def archive_case(self, case_id):
        state = self.get_case_state(case_id)
        self.cases_on_phone.remove(state)
        # I'm not quite clear on when this can happen, but we've seen it 
        # in wild, so safeguard against it.
        if not self.phone_has_dependent_case(case_id):
            self.dependent_cases_on_phone.append(state)
    
    def _phone_owns(self, action):
        # whether the phone thinks it owns an action block.
        # the only way this can't be true is if the block assigns to an
        # owner id that's not associated with the user on the phone 
        if "owner_id" in action.updated_known_properties and action.updated_known_properties["owner_id"]:
            return action.updated_known_properties["owner_id"] in self.owner_ids_on_phone
        return True
        
    def update_phone_lists(self, xform, case_list):
        # for all the cases update the relevant lists in the sync log
        # so that we can build a historical record of what's associated
        # with the phone
        for case in case_list:
            actions = case.get_actions_for_form(xform.get_id)
            for action in actions:
                try: 
                    if action.action_type == const.CASE_ACTION_CREATE:
                        self._assert(not self.phone_has_case(case._id),
                                'phone has case being created: %s' % case._id)
                        if self._phone_owns(action):
                            self.cases_on_phone.append(CaseState(case_id=case.get_id, 
                                                                 indices=[]))
                    elif action.action_type == const.CASE_ACTION_UPDATE:
                        self._assert(self.phone_has_case(case.get_id),
                                "phone doesn't have case being updated: %s" % case._id)
                        if not self._phone_owns(action):
                            # only action necessary here is in the case of 
                            # reassignment to an owner the phone doesn't own
                            self.archive_case(case.get_id)
                    elif action.action_type == const.CASE_ACTION_INDEX:
                        # in the case of parallel reassignment and index update
                        # the phone might not have the case
                        if self.phone_has_case(case.get_id):
                            case_state = self.get_case_state(case.get_id)
                        else:
                            self._assert(self.phone_has_dependent_case(case._id),
                                         "phone doesn't have referenced case: %s" % case._id)
                            case_state = self.get_dependent_case_state(case.get_id)
                        # reconcile indices
                        case_state.update_indices(action.indices)
                    elif action.action_type == const.CASE_ACTION_CLOSE:
                        if self.phone_has_case(case.get_id):
                            self.archive_case(case.get_id)
                except Exception, e:
                    # debug
                    # import pdb
                    # pdb.set_trace()
                    raise    
        self.save()
                
    def get_footprint_of_cases_on_phone(self):
        """
        Gets the phone's flat list of all case ids on the phone, 
        owned or not owned but relevant.
        """
        def children(case_state):
            return [self._get_case_state_from_anywhere(index.referenced_id) \
                    for index in case_state.indices]
        
        relevant_cases = set()
        queue = list(case_state for case_state in self.cases_on_phone)
        while queue:
            case_state = queue.pop()
            if case_state.case_id not in relevant_cases:
                relevant_cases.add(case_state.case_id)
                queue.extend(children(case_state))
        return relevant_cases
    
    def phone_is_holding_case(self, case_id):
        """
        Whether the phone is holding (not purging) a case.
        """
        # this is inefficient and could be optimized
        if self.phone_has_case(case_id): 
            return True
        else:
            cs = self.get_dependent_case_state(case_id)
            if cs and case_id in self.get_footprint_of_cases_on_phone():
                return True
            return False
            
    def get_state_hash(self):
        return CaseStateHash(Checksum(self.get_footprint_of_cases_on_phone()).hexdigest())

    def reconcile_cases(self):
        """
        Goes through the cases expected to be on the phone and reconciles
        any duplicate records.
        """
        self.cases_on_phone = list(set(self.cases_on_phone))
        self.dependent_cases_on_phone = list(set(self.dependent_cases_on_phone))

    def __unicode__(self):
        return "%s synced on %s (%s)" % (self.user_id, self.date.date(), self.get_id)

from casexml.apps.phone import signals