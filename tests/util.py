import os
import uuid
from couchforms.util import post_xform_to_couch
from corehq.apps.case.models.couch import CommCareCase

def bootstrap_case_from_xml(test_class, filename, case_id_override=None,
                                 referral_id_override=None):
    file_path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(file_path, "rb") as f:
        xml_data = f.read()
    doc_id, uid, case_id, ref_id = replace_ids_and_post(xml_data, case_id_override=case_id_override, 
                                                         referral_id_override=referral_id_override)  
    case = CommCareCase.get_by_case_id(case_id)
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
    expected_lines = expected.split("\n")
    actual_lines = actual.split(delimiter)
    test_case.assertEqual(len(expected_lines), len(actual_lines)) 
    for i in range(len(expected_lines)):
        if ignore_whitespace:
            test_case.assertEqual(expected_lines[i].strip(), actual_lines[i].strip())
        else:
            test_case.assertEqual(expected_lines[i], actual_lines[i])
        
    
    
    
    