import os
import uuid

from couchforms.util import post_xform_to_couch
from couchforms.models import XFormInstance

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import process_cases

def bootstrap_case_from_xml(test_class, filename, case_id_override=None,
                                 referral_id_override=None):
    file_path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(file_path, "rb") as f:
        xml_data = f.read()
    doc_id, uid, case_id, ref_id = replace_ids_and_post(xml_data, case_id_override=case_id_override, 
                                                         referral_id_override=referral_id_override)  
    doc = XFormInstance.get(doc_id)
    process_cases(sender="testharness", xform=doc)
    case = CommCareCase.get(case_id)
    test_class.assertEqual(case_id, case.case_id)
    return case
            
        
def replace_ids_and_post(xml_data, case_id_override=None, referral_id_override=None):
    # from our test forms, replace the UIDs so we don't get id conflicts
    uid, case_id, ref_id = (uuid.uuid4().hex for i in range(3))
    
    if case_id_override:      case_id = case_id_override
    if referral_id_override:  ref_id = referral_id_override
        
    xml_data = xml_data.replace("REPLACE_UID", uid)
    xml_data = xml_data.replace("REPLACE_CASEID", case_id)
    xml_data = xml_data.replace("REPLACE_REFID", ref_id)
    doc = post_xform_to_couch(xml_data)
    return (doc.get_id, uid, case_id, ref_id)
    
def check_xml_line_by_line(test_case, expected, actual, ignore_whitespace=True, delimiter="\n"):
    """Does what it's called, hopefully parameters are self-explanatory"""
    if ignore_whitespace:
        expected = expected.strip()
        actual = actual.strip()
    expected_lines = expected.split(delimiter)
    actual_lines = actual.split(delimiter)
    if ignore_whitespace:
        # remove empty lines, strip lines.
        expected_lines = [l.strip() for l in expected_lines if l.strip()]
        actual_lines = [l.strip() for l in actual_lines if l.strip()]
    test_case.assertEqual(len(expected_lines), len(actual_lines)) 
    for i in range(len(expected_lines)):
        test_case.assertEqual(expected_lines[i], actual_lines[i])
        
    
    
    
    