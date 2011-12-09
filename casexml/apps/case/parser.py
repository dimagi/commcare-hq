"""
This isn't really a parser, but it's the code that generates case-like
objects from things from xforms.
"""

from casexml.apps.case import const

XMLNS_ATTR = "@xmlns"

V1 = "1.0"
V2 = "2.0"
DEFAULT_VERSION = V1

NS_VERSION_MAP = {
    "http://commcarehq.org/case/transaction/v2": "2.0"
}

def get_version(case_block):
    """
    Given a case block, determine what version it is.
    """
    xmlns = case_block.get(XMLNS_ATTR, "")
    if xmlns:
        if xmlns not in NS_VERSION_MAP:
            raise CaseGenerationException("%s not a valid case xmlns. We don't know how to handle this version.")
        return NS_VERSION_MAP[xmlns]
    return DEFAULT_VERSION


class CaseGenerationException(Exception):
    """
    When anything illegal/unexpected happens while working with case parsing
    """ 
    pass

def parse_v1(case_block):
    if const.CASE_TAG_ID not in case_block:
        raise CaseGenerationException
    
    modified_on = case_block.get(const.CASE_TAG_MODIFIED, "")
    return CaseUpdate(id=case_block[const.CASE_TAG_ID], 
                      version=V1,
                      block=case_block,
                      modified_on_str=modified_on)

def _to_attr(val):
    return "@%s" % val

def parse_v2(case_block):
    case_id_attr = _to_attr(const.CASE_TAG_ID) 
    if case_id_attr not in case_block:
        raise CaseGenerationException
    
    user_id = case_block.get(_to_attr(const.CASE_TAG_USER_ID), "")
    modified_on = case_block.get(_to_attr(const.CASE_TAG_MODIFIED), "")
    return CaseUpdate(id=case_block[case_id_attr],
                      version=V2,
                      block=case_block,
                      user_id=user_id,
                      modified_on_str=modified_on)
    
VERSION_FUNCTION_MAP = {
    V1: parse_v1,
    V2: parse_v2
}

def case_update_from_block(case_block):
    case_version = get_version(case_block)
    return VERSION_FUNCTION_MAP[case_version](case_block)

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
    