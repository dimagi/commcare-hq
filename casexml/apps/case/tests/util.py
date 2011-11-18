import os
import uuid

from datetime import datetime, timedelta

from couchforms.util import post_xform_to_couch
from couchforms.models import XFormInstance

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import process_cases
from dimagi.utils.dates import utcnow_sans_milliseconds
from lxml import etree

def bootstrap_case_from_xml(test_class, filename, case_id_override=None,
                                 referral_id_override=None):
    
    starttime = utcnow_sans_milliseconds()
    
    file_path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(file_path, "rb") as f:
        xml_data = f.read()
    doc_id, uid, case_id, ref_id = replace_ids_and_post(xml_data, case_id_override=case_id_override, 
                                                         referral_id_override=referral_id_override)  
    doc = XFormInstance.get(doc_id)
    process_cases(sender="testharness", xform=doc)
    case = CommCareCase.get(case_id)
    test_class.assertTrue(starttime <= case.server_modified_on)
    test_class.assertTrue(datetime.utcnow() >= case.server_modified_on)
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
    
def check_xml_line_by_line(test_case, expected, actual):
    """Does what it's called, hopefully parameters are self-explanatory"""
    # this is totally wacky, but elementtree strips needless
    # whitespace that mindom will preserve in the original string
    parser = etree.XMLParser(remove_blank_text=True)
    parsed_expected = etree.tostring(etree.XML(expected, parser), pretty_print=True)
    parsed_actual = etree.tostring(etree.XML(actual, parser), pretty_print=True)
    
    if parsed_expected == parsed_actual:
        return
    
    try:
        expected_lines =  parsed_expected.split("\n")
        actual_lines = parsed_actual.split("\n")
        test_case.assertEqual(len(expected_lines), len(actual_lines), "Parsed xml files are different lengths\n" + 
                              "Expected: \n%s\nActual:\n%s" % (parsed_expected, parsed_actual)) 
        for i in range(len(expected_lines)):
            test_case.assertEqual(expected_lines[i], actual_lines[i])
            
    except AssertionError:
        import logging
        logging.error("Failure in xml comparison\nExpected:\n%s\nActual:\n%s" % (parsed_expected, parsed_actual))
        raise
        
    
    
    