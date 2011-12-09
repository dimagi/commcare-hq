from __future__ import absolute_import
from couchdbkit.ext.django.schema import *
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.util import get_close_case_xml, get_close_referral_xml,\
    couchable_property
from couchdbkit.schema.properties_proxy import SchemaListProperty
from datetime import datetime, date, time
from couchdbkit.ext.django.schema import *
from casexml.apps.case import const
from dimagi.utils import parsing
import logging
from receiver.util import spoof_submission
from couchforms.models import XFormInstance

"""
Couch models for commcare cases.  

For details on casexml check out:
http://bitbucket.org/javarosa/javarosa/wiki/casexml
"""

class CaseBase(Document):
    """
    Base class for cases and referrals.
    """
    opened_on = DateTimeProperty()
    modified_on = DateTimeProperty()
    type = StringProperty()
    closed = BooleanProperty(default=False)
    closed_on = DateTimeProperty()
    
    class Meta:
        app_label = 'case'

class CommCareCaseAction(DocumentSchema):
    """
    An atomic action on a case. Either a create, update, or close block in
    the xml.
    """
    action_type = StringProperty()
    date = DateTimeProperty()
    server_date = DateTimeProperty()
    xform_id = StringProperty()
    
    
    @classmethod
    def from_action_block(cls, action, date, xformdoc, action_block):
        if not action in const.CASE_ACTIONS:
            raise ValueError("%s not a valid case action!")
        
        action = CommCareCaseAction(action_type=action, date=date, 
                                    xform_id=xformdoc.get_id)
        
        # a close block can come without anything inside.  
        # if this is the case don't bother trying to post 
        # process anything
        if isinstance(action_block, basestring):
            return action
            
        for item in action_block:
            action[item] = couchable_property(action_block[item])
        return action
    
    @classmethod
    def new_create_action(cls, date=None):
        """
        Get a new create action
        """
        if not date: date = datetime.utcnow()
        return CommCareCaseAction(action_type=const.CASE_ACTION_CREATE, 
                                  date=date, 
                                  opened_on=date)
    
    @classmethod
    def new_close_action(cls, date=None):
        """
        Get a new close action
        """
        if not date: date = datetime.utcnow()
        return CommCareCaseAction(action_type=const.CASE_ACTION_CLOSE, 
                                  date=date, 
                                  closed_on=date)
    
    class Meta:
        app_label = 'case'

    
class Referral(CaseBase):
    """
    A referral, taken from casexml.  
    """
    
    # Referrals have top-level couch guids, but this id is important
    # to the phone, so we keep it here.  This is _not_ globally unique
    # but case_id/referral_id/type should be.  
    # (in our world: case_id/referral_id/type)
    referral_id = StringProperty()
    followup_on = DateTimeProperty()
    outcome = StringProperty()
    
    class Meta:
        app_label = 'case'

    def __unicode__(self):
        return ("%s:%s" % (self.type, self.referral_id))
        
    def apply_updates(self, date, referral_block):
        if not const.REFERRAL_ACTION_UPDATE in referral_block:
            logging.warn("No update action found in referral block, nothing to be applied")
            return
        
        update_block = referral_block[const.REFERRAL_ACTION_UPDATE] 
        if not self.type == update_block[const.REFERRAL_TAG_TYPE]:
            raise logging.warn("Tried to update from a block with a mismatched type!")
            return
        
        if date > self.modified_on:
            self.modified_on = date
        
        if const.REFERRAL_TAG_FOLLOWUP_DATE in referral_block:
            self.followup_on = parsing.string_to_datetime(referral_block[const.REFERRAL_TAG_FOLLOWUP_DATE])
        
        if const.REFERRAL_TAG_DATE_CLOSED in update_block:
            self.closed = True
            self.closed_on = parsing.string_to_datetime(update_block[const.REFERRAL_TAG_DATE_CLOSED])
            
            
    @classmethod
    def from_block(cls, date, block):
        """
        Create referrals from a block of processed data (a dictionary)
        """
        if not const.REFERRAL_ACTION_OPEN in block:
            raise ValueError("No open tag found in referral block!")
        id = block[const.REFERRAL_TAG_ID]
        follow_date = parsing.string_to_datetime(block[const.REFERRAL_TAG_FOLLOWUP_DATE])
        open_block = block[const.REFERRAL_ACTION_OPEN]
        types = open_block[const.REFERRAL_TAG_TYPES].split(" ")
        
        ref_list = []
        for type in types:
            ref = Referral(referral_id=id, followup_on=follow_date, 
                            type=type, opened_on=date, modified_on=date, 
                            closed=False)
            ref_list.append(ref)
        
        # there could be a single update block that closes a referral
        # that we just opened.  not sure why this would happen, but 
        # we'll support it.
        if const.REFERRAL_ACTION_UPDATE in block:
            update_block = block[const.REFERRAL_ACTION_UPDATE]
            for ref in ref_list:
                if ref.type == update_block[const.REFERRAL_TAG_TYPE]:
                    ref.apply_updates(date, block)
        
        return ref_list

class CommCareCase(CaseBase):
    """
    A case, taken from casexml.  This represents the latest
    representation of the case - the result of playing all
    the actions in sequence.
    """
    domain = StringProperty()
    xform_ids = StringListProperty()

    external_id = StringProperty()
    user_id = StringProperty()
    owner_id = StringProperty()
    
    referrals = SchemaListProperty(Referral)
    actions = SchemaListProperty(CommCareCaseAction)
    name = StringProperty()
    version = StringProperty()
    
    server_modified_on = DateTimeProperty()
    
    class Meta:
        app_label = 'case'
        
    def __unicode__(self):
        return "CommCareCase: %s (%s)" % (self.case_id, self.get_id)
    
    
    def __get_case_id(self):        return self._id
    def __set_case_id(self, id):    self._id = id
    case_id = property(__get_case_id, __set_case_id)

    def get_server_modified_date(self):
        # gets (or adds) the server modified timestamp
        if not self.server_modified_on:
            self.save()
        return self.server_modified_on
        
    def get_case_property(self, property):
        try:
            return getattr(self, property)
        except Exception:
            return None
    def set_case_property(self, property, value):
        setattr(self, property, value)

    def case_properties(self):
        return self.to_json()

    def get_actions_for_form(self, form_id):
        return [a for a in self.actions if a.xform_id == form_id]
        
    def get_version_token(self):
        """
        A unique token for this version. 
        """
        # in theory since case ids are unique and modification dates get updated
        # upon any change, this is all we need
        return "%s::%s" % (self.case_id, self.modified_on)
    
    @property
    def attachments(self):
        """
        Get any attachments associated with this.
        
        returns (creating_form_id, attachment_name) tuples 
        """
        attachments = []
        for action in self.actions:
            for prop in action.dynamic_properties():
                val = action[prop]
                # welcome to hard code city!
                if isinstance(val, dict) and "@tag" in val and val["@tag"] == "attachment":
                    attachments.append((action.xform_id, val["#text"]))
        return attachments
    
    def get_attachment(self, attachment_tuple):
        return XFormInstance.get_db().fetch_attachment(attachment_tuple[0], attachment_tuple[1])
        
    @classmethod
    def from_case_update(cls, case_update, xformdoc):
        """
        Create a case object from a case update object.
        """
        case = CommCareCase()
        case._id = case_update.id
        case.modified_on = parsing.string_to_datetime(case_update.modified_on_str) \
                            if case_update.modified_on_str else datetime.utcnow()
        
        # apply initial updates, referrals and such, if present
        case.update_from_case_update(case_update, xformdoc)
        return case
    
    def apply_create_block(self, create_block, xformdoc, modified_on):
        # create case from required fields in the case/create block
        # create block
        def _safe_replace_and_force_to_string(me, attr, dict, key):
            if getattr(me, attr, None):
                # attr exists and wasn't empty or false, for now don't do anything, 
                # though in the future we want to do a date-based modification comparison
                return
            rep = dict[key] if key in dict else None
            if rep:
                setattr(me, attr, unicode(rep))
            
        _safe_replace_and_force_to_string(self, "type", create_block, const.CASE_TAG_TYPE_ID)
        _safe_replace_and_force_to_string(self, "name", create_block, const.CASE_TAG_NAME)
        _safe_replace_and_force_to_string(self, "external_id", create_block, const.CASE_TAG_EXTERNAL_ID)
        _safe_replace_and_force_to_string(self, "user_id", create_block, const.CASE_TAG_USER_ID)
        create_action = CommCareCaseAction.from_action_block(const.CASE_ACTION_CREATE, 
                                                             modified_on, 
                                                             xformdoc,
                                                             create_block)
        self.actions.append(create_action)
    
    def update_from_case_update(self, case_update, xformdoc):
        
        mod_date = parsing.string_to_datetime(case_update.modified_on_str) \
                    if   case_update.modified_on_str else datetime.utcnow()
        
        if self.modified_on is None or mod_date > self.modified_on:
            self.modified_on = mod_date
    
        if case_update.creates_case():
            self.apply_create_block(case_update.create_block, xformdoc, mod_date)
            if not self.opened_on:
                self.opened_on = mod_date
        
        
        if case_update.updates_case():
            update_action = CommCareCaseAction.from_action_block(const.CASE_ACTION_UPDATE, 
                                                                 mod_date,
                                                                 xformdoc,
                                                                 case_update.update_block)
            self.apply_updates(update_action)
            self.actions.append(update_action)
        
        if case_update.closes_case():
            close_action = CommCareCaseAction.from_action_block(const.CASE_ACTION_CLOSE, 
                                                                mod_date, 
                                                                xformdoc,
                                                                case_update.close_block)
            self.apply_close(close_action)
            self.actions.append(close_action)
        
        if case_update.has_referrals():
            if const.REFERRAL_ACTION_OPEN in case_update.referral_block:
                referrals = Referral.from_block(mod_date, case_update.referral_block)
                # for some reason extend doesn't work.  disconcerting
                # self.referrals.extend(referrals)
                for referral in referrals:
                    self.referrals.append(referral)
            elif const.REFERRAL_ACTION_UPDATE in case_update.referral_block:
                found = False
                update_block = case_update.referral_block[const.REFERRAL_ACTION_UPDATE]
                for ref in self.referrals:
                    if ref.type == update_block[const.REFERRAL_TAG_TYPE]:
                        ref.apply_updates(mod_date, case_update.referral_block)
                        found = True
                if not found:
                    logging.error(("Tried to update referral type %s for referral %s in case %s "
                                   "but it didn't exist! Nothing will be done about this.") % \
                                   (update_block[const.REFERRAL_TAG_TYPE], 
                                    case_update.referral_block[const.REFERRAL_TAG_ID],
                                    self.case_id))
        
        # finally override any explicit properties from the update
        if case_update.user_id:     self.user_id = case_update.user_id
        if case_update.version:     self.version = case_update.version

        
    def apply_updates(self, update_action):
        """
        Applies updates to a case
        """
        if const.CASE_TAG_TYPE_ID in update_action:
            self.type = update_action[const.CASE_TAG_TYPE_ID]
        if const.CASE_TAG_NAME in update_action:
            self.name = update_action[const.CASE_TAG_NAME]
        if const.CASE_TAG_DATE_OPENED in update_action:
            self.opened_on = update_action[const.CASE_TAG_DATE_OPENED]
        for item in update_action.dynamic_properties():
            if item not in const.CASE_TAGS:
                self[item] = couchable_property(update_action[item])
            
        
    def apply_close(self, close_action):
        self.closed = True
        self.closed_on = close_action.date


    def force_close(self, submit_url):
        if not self.closed:
            submission = get_close_case_xml(time=datetime.utcnow(), case_id=self._id)
            spoof_submission(submit_url, submission, name="close.xml")

    def force_close_referral(self, submit_url, referral):
        if not referral.closed:
            submission = get_close_referral_xml(time=datetime.utcnow(), case_id=self._id, referral_id=referral.referral_id, referral_type=referral.type)
            spoof_submission(submit_url, submission, name="close_referral.xml")

    def dynamic_case_properties(self):
        """(key, value) tuples sorted by key"""
        return sorted(self.dynamic_properties().items())

    def save(self, **params):
        self.server_modified_on = datetime.utcnow()
        super(CommCareCase, self).save(**params)
        case_post_save.send(CommCareCase, case=self)

import casexml.apps.case.signals