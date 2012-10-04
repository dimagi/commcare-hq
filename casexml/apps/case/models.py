from __future__ import absolute_import
import re
from django.core.cache import cache
from casexml.apps.phone.xml import get_case_element
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.util import get_close_case_xml, get_close_referral_xml,\
    couchable_property
from datetime import datetime
from couchdbkit.ext.django.schema import *
from casexml.apps.case import const
from dimagi.utils import parsing
import logging
from dimagi.utils.indicators import ComputedDocumentMixin
from receiver.util import spoof_submission
from couchforms.models import XFormInstance
from casexml.apps.case.sharedmodels import IndexHoldingMixIn, CommCareCaseIndex
from copy import copy
import itertools
from dimagi.utils.couch.database import get_db
from couchdbkit.exceptions import ResourceNotFound

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
    action_type = StringProperty(choices=list(const.CASE_ACTIONS))
    date = DateTimeProperty()
    server_date = DateTimeProperty()
    xform_id = StringProperty()
    sync_log_id = StringProperty()
    
    updated_known_properties = DictProperty()
    updated_unknown_properties = DictProperty()
    indices = SchemaListProperty(CommCareCaseIndex)
    
    @classmethod
    def from_parsed_action(cls, action_type, date, xformdoc, action):
        if not action_type in const.CASE_ACTIONS:
            raise ValueError("%s not a valid case action!")
        
        ret = CommCareCaseAction(action_type=action_type, date=date,
                                 xform_id=xformdoc.get_id) 
        
        def _couchify(d):
            return dict((k, couchable_property(v)) for k, v in d.items())
                        
        ret.server_date = datetime.utcnow()
        ret.updated_known_properties = _couchify(action.get_known_properties())
        ret.updated_unknown_properties = _couchify(action.dynamic_properties)
        ret.indices = [CommCareCaseIndex.from_case_index_update(i) for i in action.indices]
        if hasattr(xformdoc, "last_sync_token"):
            ret.sync_log_id = xformdoc.last_sync_token
        return ret

    @property
    def xform(self):
        xform = XFormInstance.get(self.xform_id)
        return xform

    @property
    def user_id(self):
        key = 'xform-%s-user_id' % self.xform_id
        id = cache.get(key)
        if not id:
            xform = self.xform
            id = xform.metadata.userID
            cache.set(key, id, 12*60*60)
        return id
    
        
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

class CommCareCase(CaseBase, IndexHoldingMixIn, ComputedDocumentMixin):
    """
    A case, taken from casexml.  This represents the latest
    representation of the case - the result of playing all
    the actions in sequence.
    """
    domain = StringProperty()
    export_tag = StringListProperty()
    xform_ids = StringListProperty()

    external_id = StringProperty()
    user_id = StringProperty()
    owner_id = StringProperty()

    referrals = SchemaListProperty(Referral)
    actions = SchemaListProperty(CommCareCaseAction)
    name = StringProperty()
    version = StringProperty()
    indices = SchemaListProperty(CommCareCaseIndex)

    server_modified_on = DateTimeProperty()

    class Meta:
        app_label = 'case'

    def __unicode__(self):
        return "CommCareCase: %s (%s)" % (self.case_id, self.get_id)


    def __get_case_id(self):        return self._id
    def __set_case_id(self, id):    self._id = id
    case_id = property(__get_case_id, __set_case_id)

    @property
    def server_opened_on(self):
        try:
            open_action = self.actions[0]
            #assert open_action.action_type == const.CASE_ACTION_CREATE
            return open_action.server_date
        except Exception:
            pass


    @property
    def reverse_indices(self):
        def wrap_row(row):
            index = CommCareCaseIndex.wrap(row['value'])
            index.is_reverse = True
            return index
        return get_db().view("case/related",
            key=[self.domain, self.get_id, "reverse_index"],
            reduce=False,
            wrapper=wrap_row
        ).all()
        
    @property
    def all_indices(self):
        return itertools.chain(self.indices, self.reverse_indices)
        
    def get_json(self):
        
        return {
            # referrals and actions excluded here
            "domain": self.domain,
            "case_id": self.case_id,
            "user_id": self.user_id,
            "closed": self.closed,
            "date_closed": self.closed_on,
            "xform_ids": self.xform_ids,
            # renamed
            "date_modified": self.modified_on,
            "version": self.version,
            # renamed
            "server_date_modified": self.server_modified_on,
            # renamed
            "server_date_opened": self.server_opened_on,
            "properties": dict(self.dynamic_case_properties() + {
                "external_id": self.external_id,
                "owner_id": self.owner_id,
                # renamed
                "case_name": self.name,
                # renamed
                "case_type": self.type,
                # renamed
                "date_opened": self.opened_on,
                # all custom properties go here
            }.items()),
            #reorganized
            "indices": dict([
                # all indexes are stored in the following form
                (index.identifier, {
                    "case_type": index.referenced_type,
                    "case_id": index.referenced_id
                }) for index in self.indices
            ]),
            "reverse_indices": dict([
                # all indexes are stored in the following form
                (index.identifier, {
                    "case_type": index.referenced_type,
                    "case_id": index.referenced_id
                }) for index in self.reverse_indices
            ]),
        }
    
    def get_preloader_dict(self):
        """
        Gets the case as a dictionary for use in touchforms preloader framework
        """
        ret = copy(self._doc)
        ret["case-id"] = self.get_id
        return ret

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
    
    def get_forms(self):
        """
        Gets the form docs associated with a case. If it can't find a form
        it won't be included.
        """
        def _get(id):
            try:
                return XFormInstance.get(id)
            except ResourceNotFound:
                return None
        
        forms = [_get(id) for id in self.xform_ids]
        return [form for form in forms if form] 
    
    @property
    def attachments(self):
        """
        Get any attachments associated with this.
        
        returns (creating_form_id, attachment_name) tuples 
        """
        attachments = []
        for action in self.actions:
            for prop, val in action.updated_unknown_properties.items():
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
    
    def apply_create_block(self, create_action, xformdoc, modified_on):
        # create case from required fields in the case/create block
        # create block
        def _safe_replace_and_force_to_string(me, attr, val):
            if getattr(me, attr, None):
                # attr exists and wasn't empty or false, for now don't do anything, 
                # though in the future we want to do a date-based modification comparison
                return
            if val:
                setattr(me, attr, unicode(val))
            
        _safe_replace_and_force_to_string(self, "type", create_action.type)
        _safe_replace_and_force_to_string(self, "name", create_action.name)
        _safe_replace_and_force_to_string(self, "external_id", create_action.external_id)
        _safe_replace_and_force_to_string(self, "user_id", create_action.user_id)
        _safe_replace_and_force_to_string(self, "owner_id", create_action.owner_id)
        create_action = CommCareCaseAction.from_parsed_action(const.CASE_ACTION_CREATE, 
                                                              modified_on, 
                                                              xformdoc,
                                                              create_action)
        self.actions.append(create_action)
    
    def update_from_case_update(self, case_update, xformdoc):
        
        mod_date = parsing.string_to_datetime(case_update.modified_on_str) \
                    if   case_update.modified_on_str else datetime.utcnow()
        
        if self.modified_on is None or mod_date > self.modified_on:
            self.modified_on = mod_date
    
        if case_update.creates_case():
            self.apply_create_block(case_update.get_create_action(), xformdoc, mod_date)
            if not self.opened_on:
                self.opened_on = mod_date
        
        
        if case_update.updates_case():
            update_action = CommCareCaseAction.from_parsed_action(const.CASE_ACTION_UPDATE, 
                                                                  mod_date,
                                                                  xformdoc,
                                                                  case_update.get_update_action())
            self.apply_updates(update_action)
            self.actions.append(update_action)
        
        if case_update.closes_case():
            close_action = CommCareCaseAction.from_parsed_action(const.CASE_ACTION_CLOSE, 
                                                                 mod_date, 
                                                                 xformdoc,
                                                                 case_update.get_close_action())
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
        
        if case_update.has_indices():
            index_action = CommCareCaseAction.from_parsed_action(const.CASE_ACTION_INDEX, 
                                                                 mod_date,
                                                                 xformdoc,
                                                                 case_update.get_index_action())
            self.actions.append(index_action)
            self.update_indices(index_action.indices)
        
        # finally override any explicit properties from the update
        if case_update.user_id:     self.user_id = case_update.user_id
        if case_update.version:     self.version = case_update.version

        
    def apply_updates(self, update_action):
        """
        Applies updates to a case
        """
        for k, v in update_action.updated_known_properties.items():
            setattr(self, k, v)
        
        for item in update_action.updated_unknown_properties:
            if item not in const.CASE_TAGS:
                self[item] = couchable_property(update_action.updated_unknown_properties[item])
            
        
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
        return sorted([(key, value) for key, value in self.dynamic_properties().items() if re.search(r'^[a-zA-Z]', key)])

    def save(self, **params):
        self.server_modified_on = datetime.utcnow()
        super(CommCareCase, self).save(**params)
        case_post_save.send(CommCareCase, case=self)

    def to_xml(self, version):
        from xml.etree import ElementTree
        if self.closed:
            elem = get_case_element(self, ('close'), version)
        else:
            elem = get_case_element(self, ('create', 'update'), version)
        return ElementTree.tostring(elem)
    
    @classmethod
    def get_by_xform_id(cls, xform_id):
        return cls.view("case/by_xform_id", reduce=False, include_docs=True, 
                        key=xform_id)

import casexml.apps.case.signals