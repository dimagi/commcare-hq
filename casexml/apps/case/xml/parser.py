"""
This isn't really a parser, but it's the code that generates case-like
objects from things from xforms.
"""

from casexml.apps.case import const
from casexml.apps.case.xml import DEFAULT_VERSION, V1, V2, NS_REVERSE_LOOKUP_MAP

XMLNS_ATTR = "@xmlns"


def get_version(case_block):
    """
    Given a case block, determine what version it is.
    """
    xmlns = case_block.get(XMLNS_ATTR, "")
    if xmlns:
        if xmlns not in NS_REVERSE_LOOKUP_MAP:
            raise CaseGenerationException("%s not a valid case xmlns. We don't know how to handle this version.")
        return NS_REVERSE_LOOKUP_MAP[xmlns]
    return DEFAULT_VERSION


class CaseGenerationException(Exception):
    """
    When anything illegal/unexpected happens while working with case parsing
    """ 
    pass


def case_update_from_block(case_block):
    case_version = get_version(case_block)
    return VERSION_FUNCTION_MAP[case_version](case_block)


class CaseActionBase(object):
    
    def __init__(self, block, type=None, name=None, external_id=None, 
                 user_id=None, owner_id=None, opened_on=None, 
                 dynamic_properties=None):
        self.raw_block = block
        self.type = type
        self.name = name
        self.external_id = external_id
        self.user_id = user_id
        self.owner_id = owner_id
        self.opened_on = opened_on
        self.dynamic_properties = dynamic_properties
    
    def get_known_properties(self):
        prop_list = ["type", "name", "external_id", "user_id", 
                     "owner_id", "opened_on"]
        return dict((p, getattr(self, p)) for p in prop_list \
                    if getattr(self, p) is not None)
    
    @classmethod
    def _from_block_and_mapping(cls, block, mapping):
        kwargs = {}
        dynamic_properties = {}
        # if not a dict, it's probably an empty close block
        if isinstance(block, dict):
            for k, v in block.items():
                if k in mapping:
                    kwargs[mapping[k]] = v
                else:
                    dynamic_properties[k] = v 
        
        return cls(block, dynamic_properties=dynamic_properties,
                   **kwargs)
        
    @classmethod
    def from_v1(cls, block):
        mapping = {const.CASE_TAG_TYPE_ID: "type",
                   const.CASE_TAG_NAME: "name",
                   const.CASE_TAG_EXTERNAL_ID: "external_id",
                   const.CASE_TAG_USER_ID: "user_id",
                   const.CASE_TAG_OWNER_ID: "owner_id",
                   const.CASE_TAG_DATE_OPENED: "opened_on"}
        return cls._from_block_and_mapping(block, mapping)
                   
    @classmethod
    def from_v2(cls, block):
        # the only difference is the place where "type" is stored
        mapping = {const.CASE_TAG_TYPE: "type",
                   const.CASE_TAG_NAME: "name",
                   const.CASE_TAG_EXTERNAL_ID: "external_id",
                   const.CASE_TAG_USER_ID: "user_id",
                   const.CASE_TAG_OWNER_ID: "owner_id",
                   const.CASE_TAG_DATE_OPENED: "opened_on"}
        return cls._from_block_and_mapping(block, mapping)
        

class CaseCreateAction(CaseActionBase):
    # Right now this doesn't do anything other than the default
    pass

        
class CaseUpdateAction(CaseActionBase):
    # Right now this doesn't do anything other than the default
    pass

class CaseCloseAction(CaseActionBase):
    # Right now this doesn't do anything other than the default
    pass


class CaseIndex(object):
    
    def __init__(self, identifier, referenced_type, referenced_id):
        self.identifier = identifier
        self.referenced_type = referenced_type
        self.referenced_id = referenced_id
    
    @classmethod
    def from_v1(cls, block):
        # indices are not supported in v1
        return []
    
    @classmethod
    def from_v2(cls, block):
        ret = []
        for id, data in block.items():
            if "@case_type" not in data:
                raise CaseGenerationException("Invalid index, must have a case type attribute.")
            ret.append(CaseIndex(id, data["@case_type"], data.get("#text", "")))
        return ret
    
class CaseUpdate(object):
    """
    A temporary model that parses the data from the form consistently.
    The actual Case objects use this to update themselves.
    """
    
    def __init__(self, id, version, block, user_id="", modified_on_str=""):
        self.id = id
        self.version = version
        self.user_id = user_id
        self.modified_on_str = modified_on_str
        
        # deal with the various blocks
        self.raw_block = block
        self.create_block = block.get(const.CASE_ACTION_CREATE, {})
        self.update_block = block.get(const.CASE_ACTION_UPDATE, {})
        self.close_block = block.get(const.CASE_ACTION_CLOSE, {})
        self._closes_case = const.CASE_ACTION_CLOSE in block
        self.index_block = block.get(const.CASE_BLOCK_INDEX, {})
        
        # referrals? really?
        self.referral_block = block.get(const.REFERRAL_TAG, {})
        
        # actions
        self.actions = []
        if self.creates_case():
            self.actions.append(CREATE_ACTION_FUNCTION_MAP[self.version](self.create_block))
        if self.updates_case():
            self.actions.append(UPDATE_ACTION_FUNCTION_MAP[self.version](self.update_block))
        if self.closes_case():
            self.actions.append(CLOSE_ACTION_FUNCTION_MAP[self.version](self.close_block))
        
        
        self.indices = INDEX_FUNCTION_MAP[self.version](self.index_block) if self.has_indices() else []
    
    def creates_case(self):
        # creates have to have actual data in them so this is fine
        return bool(self.create_block)    
    
    def updates_case(self):
        # updates have to have actual data in them so this is fine
        return bool(self.update_block)    
    
    def closes_case(self):
        # closes might not have data and so we store this separately
        return self._closes_case    
    
    def has_indices(self):
        return bool(self.index_block)
    
    def has_referrals(self):
        return bool(self.referral_block)
    
    def __str__(self):
        return "%s: %s" % (self.version, self.id)
    
    
    def _filtered_action(self, func):
        # filters the actions, assumes exactly 0 or 1 match.
        filtered = filter(func, self.actions)
        if filtered:
            assert(len(filtered) == 1)
            return filtered[0]
            
    def get_create_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseCreateAction))
        
    def get_update_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseUpdateAction))
    
    def get_close_action(self):
        return self._filtered_action(lambda a: isinstance(a, CaseCloseAction))
    
    @classmethod
    def from_v1(cls, case_block):
        """
        Gets a case update from a version 1 case. 
        Spec: https://bitbucket.org/javarosa/javarosa/wiki/casexml
        """
        if const.CASE_TAG_ID not in case_block:
            raise CaseGenerationException
        
        modified_on = case_block.get(const.CASE_TAG_MODIFIED, "")
        return cls(id=case_block[const.CASE_TAG_ID], 
                   version=V1,
                   block=case_block,
                   modified_on_str=modified_on)
    
    @classmethod
    def from_v2(cls, case_block):
        """
        Gets a case update from a version 2 case. 
        Spec: https://bitbucket.org/commcare/commcare/wiki/casexml20
        """
        
        def _to_attr(val):
            return "@%s" % val
    
        case_id_attr = _to_attr(const.CASE_TAG_ID) 
        if case_id_attr not in case_block:
            raise CaseGenerationException
        
        user_id = case_block.get(_to_attr(const.CASE_TAG_USER_ID), "")
        modified_on = case_block.get(_to_attr(const.CASE_TAG_MODIFIED), "")
        return cls(id=case_block[case_id_attr],
                   version=V2,
                   block=case_block,
                   user_id=user_id,
                   modified_on_str=modified_on)


# this section is what maps various things to their v1/v2 parsers
VERSION_FUNCTION_MAP = {
    V1: CaseUpdate.from_v1,
    V2: CaseUpdate.from_v2
}

CREATE_ACTION_FUNCTION_MAP = {
    V1: CaseCreateAction.from_v1,
    V2: CaseCreateAction.from_v2
}

UPDATE_ACTION_FUNCTION_MAP = {
    V1: CaseUpdateAction.from_v1,
    V2: CaseUpdateAction.from_v2,
}

CLOSE_ACTION_FUNCTION_MAP = {
    V1: CaseCloseAction.from_v1,
    V2: CaseCloseAction.from_v2,
}
INDEX_FUNCTION_MAP = {
    V2: CaseIndex.from_v1,
    V2: CaseIndex.from_v2
}