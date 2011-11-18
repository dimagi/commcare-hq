from __future__ import absolute_import
import logging
from xml.sax import saxutils
from casexml.apps.case import const

def escape(o):
    if o is None:
        return ""
    else:
        return saxutils.escape(unicode(o))

def render_element(key, val):
    if isinstance(val, dict):
        elem_val = val.get('#text', '')
        attr_list = ['%s="%s"' % (x[1:], val[x]) for x in filter(lambda x: x != '#text', val.keys())]
        if len(attr_list) == 0:
            attr_string = ''
        else:
            attr_string = ' ' + ' '.join(attr_list)
        return "<%(key)s%(attrs)s>%(val)s</%(key)s>" % {"key": key, 'attrs': attr_string, "val": escape(elem_val)}
    else:
        return "<%(key)s>%(val)s</%(key)s>" % {"key": key, "val": escape(val)}


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

CASE_TEMPLATE = \
"""
<case>
    <case_id>%(case_id)s</case_id> 
    <date_modified>%(date_modified)s</date_modified>%(create_block)s%(update_block)s%(referral_block)s
</case>"""

CREATE_BLOCK = \
"""
    <create>%(base_data)s
    </create>"""

BASE_DATA = \
"""
        <case_type_id>%(case_type_id)s</case_type_id> 
        <user_id>%(user_id)s</user_id> 
        <case_name>%(case_name)s</case_name> 
        <external_id>%(external_id)s</external_id>"""

UPDATE_BLOCK = \
"""
    <update>%(update_base_data)s
        %(update_custom_data)s
    </update>"""


REFERRAL_BLOCK = \
"""
    <referral> 
        <referral_id>%(ref_id)s</referral_id>
        <followup_date>%(fu_date)s</followup_date>%(open_block)s%(update_block)s
    </referral>"""

REFERRAL_OPEN_BLOCK = \
"""
        <open>
            <referral_types>%(ref_type)s</referral_types>
        </open>"""

REFERRAL_UPDATE_BLOCK = \
"""
    <update>
        <referral_type>%(ref_type)s</referral_type>%(close_data)s
    </update>"""

REFERRAL_CLOSE_BLOCK = \
"""
        <date_closed>%(close_date)s</date_closed>"""
     
def date_to_xml_string(date):
    if date: return date.strftime("%Y-%m-%d")
    return ""

def get_referral_xml(referral):
    # TODO: support referrals not always opening, this will
    # break with sync
    open_block = REFERRAL_OPEN_BLOCK % {"ref_type": escape(referral.type)}
    
    if referral.closed:
        close_data = REFERRAL_CLOSE_BLOCK % {"close_date": escape(date_to_xml_string(referral.closed_on))}
        update_block = REFERRAL_UPDATE_BLOCK % {"ref_type": escape(referral.type),
                                                "close_data": close_data}
    else:
        update_block = "" # TODO
    return REFERRAL_BLOCK % {"ref_id": escape(referral.referral_id),
                             "fu_date": escape(date_to_xml_string(referral.followup_on)),
                             "open_block": open_block,
                             "update_block": update_block,
                             }

def get_case_xml(case, updates):
    if case is None: 
        logging.error("Can't generate case xml for empty case!")
        return ""
    
    base_data = BASE_DATA % {"case_type_id": escape(case.type),
                             "user_id": escape(case.user_id),
                             "case_name": escape(case.name),
                             "external_id": escape(case.external_id) }
    # if creating, the base data goes there, otherwise it goes in the
    # update block
    if const.CASE_ACTION_CREATE in updates:
        # currently the below code relies on the assumption that
        # every create also includes an update
        assert(const.CASE_ACTION_UPDATE in updates)
        create_block = CREATE_BLOCK % {"base_data": base_data }
        update_base_data = ""
    elif const.CASE_ACTION_UPDATE in updates:
        create_block = ""
        update_base_data = base_data
    elif const.CASE_ACTION_PURGE in updates or const.CASE_ACTION_CLOSE in updates:
        # likewise, for now we assume that you can't both create/update and close/purge  
        assert(const.CASE_ACTION_UPDATE not in updates)
        assert(const.CASE_ACTION_CREATE not in updates)
        raise NotImplemented("Need to do purging")
        
    update_custom_data = "\n\t".join([render_element(key,val)  \
                                    for key, val in case.dynamic_case_properties()])
    update_block = UPDATE_BLOCK % { "update_base_data": update_base_data,
                                    "update_custom_data": update_custom_data}
    referral_block = "".join([get_referral_xml(ref) for ref in case.referrals])
    return CASE_TEMPLATE % {"case_id": escape(case.case_id),
                            "date_modified": escape(date_to_xml_string(case.modified_on)),
                            "create_block": create_block,
                            "update_block": update_block,
                            "referral_block": referral_block
                            } 
    
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

