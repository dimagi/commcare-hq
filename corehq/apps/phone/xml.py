import logging
from corehq.apps.users.util import couch_user_from_django_user,\
    commcare_account_from_django_user, raw_username


# Response template according to 
# https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest

RESPONSE_TEMPLATE = \
'''<?xml version='1.0' encoding='UTF-8'?>
<OpenRosaResponse xmlns="http://openrosa.org/http/response">
    <message>%(message)s</message>%(extra_xml)s
</OpenRosaResponse>'''

def get_response(message, extra_xml=""):
    return RESPONSE_TEMPLATE % {"message": message,
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
    return SYNC_TEMPLATE % {"restore_id": restore_id} 

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
    open_block = REFERRAL_OPEN_BLOCK % {"ref_type": referral.type}
    
    if referral.closed:
        close_data = REFERRAL_CLOSE_BLOCK % {"close_date": date_to_xml_string(referral.closed_on)} 
        update_block = REFERRAL_UPDATE_BLOCK % {"ref_type": referral.type,
                                                "close_data": close_data}
    else:
        update_block = "" # TODO
    return REFERRAL_BLOCK % {"ref_id": referral.referral_id,
                             "fu_date": date_to_xml_string(referral.followup_on),
                             "open_block": open_block,
                             "update_block": update_block,
                             }

def get_case_xml(phone_case, create=True):
    if phone_case is None: 
        logging.error("Can't generate case xml for empty case!")
        return ""
    
    base_data = BASE_DATA % {"case_type_id": phone_case.type,
                             "user_id": phone_case.user_id,
                             "case_name": phone_case.name,
                             "external_id": phone_case.external_id }
    # if creating, the base data goes there, otherwise it goes in the
    # update block
    if create:
        create_block = CREATE_BLOCK % {"base_data": base_data }
        update_base_data = ""
    else:
        create_block = ""
        update_base_data = base_data
    
    update_custom_data = "\n        ".join(["<%(key)s>%(val)s</%(key)s>" % {"key": key, "val": val} \
                                    for key, val in phone_case.dynamic_case_properties()])
    update_block = UPDATE_BLOCK % { "update_base_data": update_base_data,
                                    "update_custom_data": update_custom_data}
    referral_block = "".join([get_referral_xml(ref) for ref in phone_case.referrals])
    return CASE_TEMPLATE % {"case_id": phone_case.case_id,
                            "date_modified": date_to_xml_string(phone_case.modified_on),
                            "create_block": create_block,
                            "update_block": update_block,
                            "referral_block": referral_block
                            } 