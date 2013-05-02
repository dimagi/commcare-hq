"""
Functions that transform known data types in HQ
"""
from dimagi.utils.data.generator import random_fullname, random_phonenumber,\
    username_from_name
from corehq.apps.users.models import CommCareUser
from corehq.apps.domainsync.deidentification.forms import deidentify_form
from casexml.apps.case.models import CommCareCase
from corehq.apps.domainsync.deidentification.apps import deidentify_app

def identity(doc):
    """
    Does nothing.
    """
    return doc

def deidentify_case_action(action):
    # v1
    if hasattr(action, "case_name"):
        action.case_name = random_fullname()
    # v2
    if "case_name" in action.updated_known_properties:
        action.updated_known_properties["case_name"] = random_fullname()
    
def deidentify_case(doc):
    assert(doc.doc["doc_type"] == "CommCareCase")
    case = CommCareCase.wrap(doc.doc)
    case.name = random_fullname()
    for action in case.actions:
        deidentify_case_action(action)
    doc.doc = case._doc
    return doc

def deidentify_commcare_user(doc):
    assert(doc.doc["doc_type"] == "CommCareUser")
    user = CommCareUser.wrap(doc.doc)
    for i in range(len(user.phone_numbers)):
        user.phone_numbers[i] = random_phonenumber()
    
    name = random_fullname()
    user.first_name = name.split(" ")[0]
    user.last_name = name.split(" ")[1]
    user.username = username_from_name(name)
    doc.doc = user._doc
    return doc

def deidentify_domain(doc):
    handleable_types = {"CommCareCase": deidentify_case,
                        "Application": deidentify_app,
                        "CommCareUser": deidentify_commcare_user,
                        "XFormInstance": deidentify_form,
                        "SavedExportSchema": identity}
    if "doc_type" in doc.doc and doc.doc["doc_type"] in handleable_types:
        return handleable_types[doc.doc["doc_type"]](doc)
        