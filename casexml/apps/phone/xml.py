from __future__ import absolute_import
import logging
from xml.sax import saxutils
from xml.etree import ElementTree
from casexml.apps.case import const

def escape(o):
    if o is None:
        return ""
    else:
        return saxutils.escape(unicode(o))

def _safe_el(tag, text=None):
    # save some typing/space
    if text:
        e = ElementTree.Element(tag)
        e.text = unicode(text)
        return e
    else:
        return ElementTree.Element(tag)
        
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


# Response template according to 
# https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest

RESPONSE_TEMPLATE = \
'''<?xml version='1.0' encoding='UTF-8'?>
<OpenRosaResponse xmlns="http://openrosa.org/http/response">
    <message>%(message)s</message>%(extra_xml)s
</OpenRosaResponse>'''

def get_response(message, extra_xml=""):
    return RESPONSE_TEMPLATE % {"message": escape(message),
                                "extra_xml": extra_xml}


RESTOREDATA_TEMPLATE =\
"""%(sync_info)s%(registration)s%(case_list)s
"""

SYNC_TEMPLATE =\
"""
    <Sync xmlns="http://commcarehq.org/sync">
        <restore_id>%(restore_id)s</restore_id> 
    </Sync>"""
    

def get_sync_xml(restore_id):
    return SYNC_TEMPLATE % {"restore_id": escape(restore_id)}

     
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
    return ElementTree.tostring(get_case_element(case, updates))
    
REGISTRATION_TEMPLATE = \
"""
    <Registration xmlns="http://openrosa.org/user/registration">
        <username>%(username)s</username>
        <password>%(password)s</password>
        <uuid>%(uuid)s</uuid>
        <date>%(date)s</date>%(user_data)s
    </Registration>"""

USER_DATA_TEMPLATE = \
"""
        <user_data>
            %(data)s
        </user_data>"""

def get_registration_xml(user):
    # TODO: this doesn't feel like a final way to do this
    # all dates should be formatted like YYYY-MM-DD (e.g. 2010-07-28)
    return REGISTRATION_TEMPLATE % {"username":  escape(user.username),
                                    "password":  escape(user.password),
                                    "uuid":      escape(user.user_id),
                                    "date":      escape(user.date_joined.strftime("%Y-%m-%d")),
                                    "user_data": get_user_data_xml(user.user_data)
                                    }
def get_user_data_xml(dict):
    if not dict:  return ""
    return USER_DATA_TEMPLATE % \
        {"data": "\n\t".join('<data key="%(key)s">%(value)s</data>' % \
                                       {"key": key, "value": escape(val) } for key, val in dict.items())}

