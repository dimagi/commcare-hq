from __future__ import absolute_import
import logging
from xml.sax import saxutils
from xml.etree import ElementTree
from casexml.apps.case import const

USER_REGISTRATION_XMLNS = "http://openrosa.org/user/registration"
SYNC_XMLNS = "http://commcarehq.org/sync"

def escape(o):
    if o is None:
        return ""
    else:
        return saxutils.escape(unicode(o))

def _safe_el(tag, text=None):
    # shortcut for commonly used functionality
    if text:
        e = ElementTree.Element(tag)
        e.text = unicode(text)
        return e
    else:
        return ElementTree.Element(tag)

def tostring(element):
    # save some typing, force UTF-8
    return ElementTree.tostring(element, encoding="utf-8")

def get_element(key, val):
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



def get_sync_element(restore_id):
    elem = _safe_el("Sync")
    elem.attrib = {"xmlns": SYNC_XMLNS}
    elem.append(_safe_el("restore_id", restore_id))
    return elem

def date_to_xml_string(date):
    if date: return date.strftime("%Y-%m-%d")
    return ""

def get_referral_element(referral):
    elem = _safe_el("referral")
    elem.append(_safe_el("referral_id", referral.referral_id))
    elem.append(_safe_el("followup_date", date_to_xml_string(referral.followup_on)))
    
    # TODO: support referrals not always opening, this will
    # break with sync
    open_block = _safe_el("open")
    open_block.append(_safe_el("referral_types", referral.type))
    elem.append(open_block)
    
    if referral.closed:
        update = _safe_el("update")
        update.append(_safe_el("referral_type", referral.type))
        update.append(_safe_el("date_closed", date_to_xml_string(referral.closed_on)))
        elem.append(update)
    
    return elem

def get_case_element(case, updates):
    if case is None: 
        logging.error("Can't generate case xml for empty case!")
        return ""
    
    root = _safe_el("case")
    root.append(_safe_el("case_id", case.get_id))
    root.append(_safe_el("date_modified", date_to_xml_string(case.modified_on)))
    
    def _add_base_properties(element, case):
        element.append(_safe_el("case_type_id", case.type))
        element.append(_safe_el("user_id", case.user_id))
        element.append(_safe_el("case_name", case.name))
        element.append(_safe_el("external_id", case.external_id))
    
    # if creating, the base data goes there, otherwise it goes in the
    # update block
    do_create = const.CASE_ACTION_CREATE in updates
    do_update = const.CASE_ACTION_UPDATE in updates
    do_purge = const.CASE_ACTION_PURGE in updates or const.CASE_ACTION_CLOSE in updates
    if do_create:
        # currently the below code relies on the assumption that
        # every create also includes an update
        create_block = _safe_el("create")
        _add_base_properties(create_block, case)
        root.append(create_block)
    
    if do_update:
        update_block = _safe_el("update")
        # if we don't have a create block, also put the base properties
        # in the update block, in case they changed
        if not do_create:
            _add_base_properties(update_block, case)
        
        # custom properties
        for k, v, in case.dynamic_case_properties():
            update_block.append(get_element(k, v))
        if case.owner_id:
            update_block.append(get_element('owner_id', case.owner_id))
            
        root.append(update_block)
    if do_purge:
        # likewise, for now we assume that you can't both create/update and close/purge  
        assert(const.CASE_ACTION_UPDATE not in updates)
        assert(const.CASE_ACTION_CREATE not in updates)
        purge_block = _safe_el("close")
        root.append(purge_block)
        
    if not do_purge:
        # only send down referrals if the case is not being purged
        for ref_elem in [get_referral_element(ref) for ref in case.referrals]:
            root.append(ref_elem)
        
    return root

def get_case_xml(case, updates):
    return tostring(get_case_element(case, updates))
    

def get_registration_element(user):
    root = _safe_el("Registration")
    root.attrib = { "xmlns": USER_REGISTRATION_XMLNS }
    root.append(_safe_el("username", user.username))
    root.append(_safe_el("password", user.password))
    root.append(_safe_el("uuid", user.user_id))
    root.append(_safe_el("date", date_to_xml_string(user.date_joined)))
    if user.user_data:
        root.append(get_user_data_element(user.user_data))
    return root

def get_registration_xml(user):
    return tostring(get_registration_element(user))
    
def get_user_data_element(dict):
    elem = _safe_el("user_data")
    for k, v in dict.items():
        sub_el = _safe_el("data", v)
        sub_el.attrib = {"key": k}
        elem.append(sub_el)
    return elem