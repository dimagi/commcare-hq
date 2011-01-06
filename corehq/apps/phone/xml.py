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
    <user_data>%(data)s
    </user_data>
"""

def get_sync_xml(restore_id):
    return SYNC_TEMPLATE % {"restore_id": restore_id} 

def get_user_data_xml(dict):
    if not dict:  return ""
    return USER_DATA_TEMPLATE % \
        {"data": "\n".join('<data key="%(key)s">%(value)s</data>' % \
                           {"key": key, "value": val } for key, val in dict.items())}    

def get_registration_xml(user):
    commcare_account = commcare_account_from_django_user(user)
    # TODO: this doesn't feel like a final way to do this
            
    # all dates should be formatted like YYYY-MM-DD (e.g. 2010-07-28)
    return REGISTRATION_TEMPLATE % {"username":  raw_username(user.username),
                                    "password":  user.password,
                                    "uuid":      commcare_account.UUID,
                                    "date":      user.date_joined.strftime("%Y-%m-%d"),
                                    "user_data": get_user_data_xml(commcare_account.user_data)
                                    }

CASE_TEMPLATE = \
"""
<case>
    <case_id>%(case_id)s</case_id> 
    <date_modified>%(date_modified)s</date_modified>%(create_block)s%(update_block)s
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
        <first_name>%(first_name)s</first_name>
        <last_name>%(last_name)s</last_name>
        <birth_date>%(birth_date)s</birth_date>
        <birth_date_est>%(birth_date_est)s</birth_date_est>
        <age>%(age)s</age>
        <sex>%(sex)s</sex>
        <village>%(village)s</village>
        <contact>%(contact)s</contact>
        <followup_type>%(followup_type)s</followup_type>
        <activation_date>%(activation_date)s</activation_date>
        <due_date>%(due_date)s</due_date>
        <missed_appt_date>%(missed_appt_date)s</missed_appt_date>
    </update>"""

def date_to_xml_string(date):
        if date: return date.strftime("%Y-%m-%d")
        return ""
    
def get_case_xml(phone_case, create=True):
    if phone_case is None: 
        logging.error("Can't generate case xml for empty case!")
        return ""
    
    base_data = BASE_DATA % {"case_type_id": phone_case.case_type_id,
                             "user_id": phone_case.user_id,
                             "case_name": phone_case.case_name,
                             "external_id": phone_case.external_id }
    # if creating, the base data goes there, otherwise it goes in the
    # update block
    if create:
        create_block = CREATE_BLOCK % {"base_data": base_data }
        update_base_data = ""
    else:
        create_block = ""
        update_base_data = base_data
    
    update_block = UPDATE_BLOCK % { "update_base_data": update_base_data,
                                    "first_name": phone_case.first_name,
                                    "last_name": phone_case.last_name,
                                    "birth_date": date_to_xml_string(phone_case.birth_date),
                                    "birth_date_est": phone_case.birth_date_est, 
                                    "age": phone_case.age, 
                                    "sex": phone_case.sex,
                                    "village": phone_case.village,
                                    "contact": phone_case.contact,
                                    "bhoma_case_id": phone_case.bhoma_case_id,
                                    "bhoma_patient_id": phone_case.bhoma_patient_id,
                                    "followup_type": phone_case.followup_type,
                                    "orig_visit_type": phone_case.orig_visit_type,
                                    "orig_visit_diagnosis": phone_case.orig_visit_diagnosis,
                                    "orig_visit_date": date_to_xml_string(phone_case.orig_visit_date),
                                    "activation_date": date_to_xml_string(phone_case.activation_date),
                                    "due_date": date_to_xml_string(phone_case.due_date),
                                    "missed_appt_date": date_to_xml_string(phone_case.missed_appt_date),
                                  }
    return CASE_TEMPLATE % {"case_id": phone_case.case_id,
                            "date_modified": date_to_xml_string(phone_case.date_modified),
                            "create_block": create_block,
                            "update_block": update_block
                            } 
