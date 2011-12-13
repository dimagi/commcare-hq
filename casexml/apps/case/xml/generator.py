from casexml.apps.case.xml import V1, V2, check_version, V2_NAMESPACE
from xml.etree import ElementTree
import logging

def safe_element(tag, text=None):
    # shortcut for commonly used functionality
    # bad! copied from the phone's XML module
    if text:
        e = ElementTree.Element(tag)
        e.text = unicode(text)
        return e
    else:
        return ElementTree.Element(tag)

def date_to_xml_string(date):
    if date: return date.strftime("%Y-%m-%d")
    return ""


def get_dynamic_element(key, val):
    """
    Gets an element from a key/value pair assumed to be pulled from 
    a case object (usually in the dynamic properties)
    """ 
    element = ElementTree.Element(key)
    if isinstance(val, dict):
        element.text = val.get('#text', '')
        element.attrs = dict([(x[1:], val[x]) for x in \
                              filter(lambda x: x and x.startswith("@"), val.keys())])
    else:
        # assume it's a string. Hopefully this is valid
        element.text = unicode(val)
    return element

class CaseXMLGeneratorBase(object):
    # The breakdown of functionality here is a little sketchy, but basically
    # everything that changed from v1 to v2 gets a split. The rest is 
    # attempted to be as DRY as possible
    
    def __init__(self, case):
        self.case = case
    
    # Force subclasses to override any methods that we don't explictly
    # want to implement in the base class. However fill in a lot ourselves.
    def _ni(self):
        raise NotImplementedError("That method must be overridden by subclass!")
    
    def get_root_element(self):
        self._ni()
    
    def get_create_element(self):
        return safe_element("create")
    
    def get_update_element(self):
        return safe_element("update")
    
    def get_close_element(self):
        return safe_element("close")
    
    def get_referral_element(self, referral):
        elem = safe_element("referral")
        elem.append(safe_element("referral_id", referral.referral_id))
        elem.append(safe_element("followup_date", date_to_xml_string(referral.followup_on)))
        
        # TODO: support referrals not always opening, this will
        # break with sync
        open_block = safe_element("open")
        open_block.append(safe_element("referral_types", referral.type))
        elem.append(open_block)
        
        if referral.closed:
            update = safe_element("update")
            update.append(safe_element("referral_type", referral.type))
            update.append(safe_element("date_closed", date_to_xml_string(referral.closed_on)))
            elem.append(update)
        
        return elem

    
    def get_case_type_element(self):
        self._ni()
    
    def get_user_id_element(self):
        return safe_element("user_id", self.case.user_id)
    
    def get_case_name_element(self):
        return safe_element("case_name", self.case.name)
    
    def get_external_id_element(self):
        return safe_element("external_id", self.case.external_id)
    
    def add_base_properties(self, element):
        element.append(self.get_case_type_element())
        element.append(self.get_case_name_element())
    
    def add_custom_properties(self, element):
        for k, v, in self.case.dynamic_case_properties():
            element.append(get_dynamic_element(k, v))
            
    def add_referrals(self, element):
        self._ni()
        
class V1CaseXMLGenerator(CaseXMLGeneratorBase):
    
    def get_root_element(self):
        root = safe_element("case")
        # moved to attrs in v2
        root.append(safe_element("case_id", self.case.get_id))
        root.append(safe_element("date_modified", date_to_xml_string(self.case.modified_on)))
        return root
    
    def get_case_type_element(self):
        return safe_element("case_type_id", self.case.type)
    
    def add_base_properties(self, element):
        element.append(self.get_case_type_element())
        # moved in v2
        element.append(self.get_user_id_element())
        element.append(self.get_case_name_element())
        # deprecated in v2
        element.append(self.get_external_id_element())
    
    def add_custom_properties(self, element):
        if self.case.owner_id:
            element.append(safe_element('owner_id', self.case.owner_id))
        super(V1CaseXMLGenerator, self).add_custom_properties(element)
        
    def add_referrals(self, element):
        for ref in self.case.referrals:
            element.append(self.get_referral_element(ref))
    
class V2CaseXMLGenerator(CaseXMLGeneratorBase):
    
    
    def get_root_element(self):
        root = safe_element("case")
        root.attrib = {"xmlns": V2_NAMESPACE,
                       "case_id": self.case.get_id,
                       "user_id": self.case.user_id,
                       "date_modified": date_to_xml_string(self.case.modified_on)}
        return root
        
    
    def get_case_type_element(self):
        # case_type_id --> case_type
        return safe_element("case_type", self.case.type)
    
    def add_base_properties(self, element):
        super(V2CaseXMLGenerator, self).add_base_properties(element)
        # owner id introduced in v2
        if self.case.owner_id:
            element.append(safe_element('owner_id', self.case.owner_id))
        
    def add_custom_properties(self, element):
        if self.case.external_id:
            element.append(safe_element('external_id', self.case.external_id))
        super(V2CaseXMLGenerator, self).add_custom_properties(element)
            
    def add_referrals(self, element):
        if self.case.referrals:
            logging.warning("Tried to add referrals to version 2 CaseXML. This is not supported")
        # intentionally a no-op
    
def get_generator(version, case):
    check_version(version)
    return GENERATOR_MAP[version](case)

GENERATOR_MAP = {
    V1: V1CaseXMLGenerator,
    V2: V2CaseXMLGenerator
}
