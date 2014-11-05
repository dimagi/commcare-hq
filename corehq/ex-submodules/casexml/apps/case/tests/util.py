import os
import uuid
from datetime import datetime
from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound

from dimagi.utils.couch.database import safe_delete
from dimagi.utils.dates import utcnow_sans_milliseconds
from lxml import etree

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V1, V2, NS_VERSION_MAP
from casexml.apps.phone.models import SyncLog
from couchforms.tests.testutils import post_xform_to_couch
from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import process_cases
from casexml.apps.phone.restore import RestoreConfig
from casexml.apps.case.util import post_case_blocks


def bootstrap_case_from_xml(test_class, filename, case_id_override=None,
                            referral_id_override=None, domain=None):
    
    starttime = utcnow_sans_milliseconds()
    
    file_path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(file_path, "rb") as f:
        xml_data = f.read()
    doc, uid, case_id, ref_id = replace_ids_and_post(
        xml_data,
        case_id_override=case_id_override,
        referral_id_override=referral_id_override,
    )
    if domain:
        doc.domain = domain
    process_cases(doc)
    case = CommCareCase.get(case_id)
    test_class.assertLessEqual(starttime, case.server_modified_on)
    test_class.assertGreaterEqual(datetime.utcnow(), case.server_modified_on)
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
    return (doc, uid, case_id, ref_id)

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
        expected_lines = parsed_expected.split("\n")
        actual_lines = parsed_actual.split("\n")
        test_case.assertEqual(
            len(expected_lines),
            len(actual_lines),
            "Parsed xml files are different lengths\n" +
            "Expected: \n%s\nActual:\n%s" % (parsed_expected, parsed_actual))

        for i in range(len(expected_lines)):
            test_case.assertEqual(expected_lines[i], actual_lines[i])

    except AssertionError:
        import logging
        logging.error("Failure in xml comparison\nExpected:\n%s\nActual:\n%s" % (parsed_expected, parsed_actual))
        raise


def assert_user_has_case(testcase, user, case_id, **kwargs):
    return check_user_has_case(testcase, user, CaseBlock(case_id=case_id, version=V2).as_xml(),
                               should_have=True, line_by_line=False, version=V2, **kwargs)


def assert_user_doesnt_have_case(testcase, user, case_id, **kwargs):
    return check_user_has_case(testcase, user, CaseBlock(case_id=case_id).as_xml(),
                               should_have=False, version=V2, **kwargs)


def check_user_has_case(testcase, user, case_block, should_have=True,
                        line_by_line=True, restore_id="", version=V1,
                        purge_restore_cache=False):

    XMLNS = NS_VERSION_MAP.get(version, 'http://openrosa.org/http/response')
    case_block.set('xmlns', XMLNS)
    case_block = ElementTree.fromstring(ElementTree.tostring(case_block))

    if restore_id and purge_restore_cache:
        SyncLog.get(restore_id).invalidate_cached_payloads()
    payload_string = RestoreConfig(user, restore_id, version=version).get_payload()
    payload = ElementTree.fromstring(payload_string)
    
    blocks = payload.findall('{{{0}}}case'.format(XMLNS))
    def get_case_id(block):
        if version == V1:
            return block.findtext('{{{0}}}case_id'.format(XMLNS))
        else:
            return block.get('case_id')
    case_id = get_case_id(case_block)
    n = 0
    def extra_info():
        return "\n%s\n%s" % (ElementTree.tostring(case_block), map(ElementTree.tostring, blocks))
    match = None
    for block in blocks:
        if get_case_id(block) == case_id:
            if should_have:
                if line_by_line:
                    check_xml_line_by_line(testcase, ElementTree.tostring(case_block), ElementTree.tostring(block))
                match = block
                n += 1
                if n == 2:
                    testcase.fail("Block for case_id '%s' appears twice in ota restore for user '%s':%s" % (case_id, user.username, extra_info()))
            else:
                testcase.fail("User '%s' gets case '%s' but shouldn't:%s" % (user.username, case_id, extra_info()))
    if not n and should_have:
        testcase.fail("Block for case_id '%s' doesn't appear in ota restore for user '%s':%s" \
                      % (case_id, user.username, extra_info()))
    return match

DEFAULT_TEST_TYPE = 'test'

def post_util(create=False, case_id=None, user_id=None, owner_id=None,
              case_type=None, version=V2, form_extras=None, close=False,
              **kwargs):

    uid = lambda: uuid.uuid4().hex
    case_id = case_id or uid()
    block = CaseBlock(create=create,
                      case_id=case_id,
                      user_id=user_id or uid(),
                      owner_id=owner_id or uid(),
                      case_type=case_type or DEFAULT_TEST_TYPE,
                      version=version,
                      update=kwargs,
                      close=close).as_xml()
    form_extras = form_extras or {}
    post_case_blocks([block], form_extras)
    return case_id


def _delete_all(db, viewname, id_func=None):
    for row in db.view(viewname, reduce=False):
        try:
            safe_delete(db, id_func(row) if id_func else row['id'])
        except ResourceNotFound:
            pass

def delete_all_cases():
    # handle with care
    _delete_all(CommCareCase.get_db(), 'case/get_lite')

def delete_all_xforms():
    # handle with care
    _delete_all(XFormInstance.get_db(), 'case/by_xform_id', id_func=lambda row: row['key'])

def delete_all_sync_logs():
    # handle with care
    _delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')
