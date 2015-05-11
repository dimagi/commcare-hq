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
from casexml.apps.case.xform import process_cases
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from casexml.apps.case.util import post_case_blocks
from django.conf import settings


class RestoreCaseBlock(object):
    """
    Little shim class for working with XML case blocks in a restore payload
    """

    def __init__(self, xml_element, version=V2):
        self.xml_element = xml_element
        self.version = version

    def to_string(self):
        return ElementTree.tostring(self.xml_element)

    def get_case_id(self):
        if self.version == V1:
            return self.xml_element.findtext('{{{0}}}case_id'.format(get_case_xmlns(self.version)))
        else:
            return self.xml_element.get('case_id')

    def get_case_name(self):
        assert self.version == V2, 'get_case_name not yet supported for legacy V1 casexml'
        # note: there has to be a better way to work with namespaced xpath.... right?!?!
        return self.xml_element.findtext('{{{0}}}create/{{{0}}}case_name'.format(get_case_xmlns(self.version)))


def bootstrap_case_from_xml(test_class, filename, case_id_override=None, domain=None):
    starttime = utcnow_sans_milliseconds()
    
    file_path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(file_path, "rb") as f:
        xml_data = f.read()
    doc, uid, case_id = _replace_ids_and_post(
        xml_data,
        case_id_override=case_id_override,
    )
    if domain:
        doc.domain = domain
    process_cases(doc)
    case = CommCareCase.get(case_id)
    test_class.assertLessEqual(starttime, case.server_modified_on)
    test_class.assertGreaterEqual(datetime.utcnow(), case.server_modified_on)
    test_class.assertEqual(case_id, case.case_id)
    return case


def _replace_ids_and_post(xml_data, case_id_override=None):
    # from our test forms, replace the UIDs so we don't get id conflicts
    uid, case_id = (uuid.uuid4().hex for i in range(2))
    
    if case_id_override:
        case_id = case_id_override

    xml_data = xml_data.replace("REPLACE_UID", uid)
    xml_data = xml_data.replace("REPLACE_CASEID", case_id)
    doc = post_xform_to_couch(xml_data)
    return (doc, uid, case_id)


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
    return assert_user_has_cases(testcase, user, [case_id], return_single=True, **kwargs)


def assert_user_has_cases(testcase, user, case_ids, **kwargs):
    case_blocks = [CaseBlock(case_id=case_id, version=V2).as_xml() for case_id in case_ids]
    return check_user_has_case(testcase, user, case_blocks,
                               should_have=True, line_by_line=False, version=V2, **kwargs)


def assert_user_doesnt_have_case(testcase, user, case_id, **kwargs):
    return assert_user_doesnt_have_cases(testcase, user, [case_id], return_single=True, **kwargs)


def assert_user_doesnt_have_cases(testcase, user, case_ids, **kwargs):
    case_blocks = [CaseBlock(case_id=case_id).as_xml() for case_id in case_ids]
    return check_user_has_case(testcase, user, case_blocks,
                               should_have=False, version=V2, **kwargs)


def get_case_xmlns(version):
    return NS_VERSION_MAP.get(version, 'http://openrosa.org/http/response')


def extract_caseblocks_from_xml(payload_string, version=V2):
    parsed_payload = ElementTree.fromstring(payload_string)
    xml_blocks = parsed_payload.findall('{{{0}}}case'.format(get_case_xmlns(version)))
    return [RestoreCaseBlock(b, version) for b in xml_blocks]


def check_user_has_case(testcase, user, case_blocks, should_have=True,
                        line_by_line=True, restore_id="", version=V1,
                        purge_restore_cache=False, return_single=False):

    if not isinstance(case_blocks, list):
        case_blocks = [case_blocks]
        return_single = True

    XMLNS = NS_VERSION_MAP.get(version, 'http://openrosa.org/http/response')

    if restore_id and purge_restore_cache:
        SyncLog.get(restore_id).invalidate_cached_payloads()
    restore_config = RestoreConfig(user=user, params=RestoreParams(restore_id, version=version))
    payload_string = restore_config.get_payload().as_string()
    blocks = extract_caseblocks_from_xml(payload_string, version)

    def check_block(case_block):
        case_block.set('xmlns', XMLNS)
        case_block = RestoreCaseBlock(ElementTree.fromstring(ElementTree.tostring(case_block)), version=version)
        case_id = case_block.get_case_id()
        n = 0

        def extra_info():
            return "\n%s\n%s" % (case_block.to_string(), map(ElementTree.tostring, blocks))
        match = None
        for block in blocks:
            if block.get_case_id() == case_id:
                if should_have:
                    if line_by_line:
                        check_xml_line_by_line(
                            testcase,
                            case_block.to_string(),
                            block.to_string(),
                        )
                    match = block
                    n += 1
                    if n == 2:
                        testcase.fail(
                            "Block for case_id '%s' appears twice"
                            " in ota restore for user '%s':%s" % (case_id, user.username, extra_info())
                        )
                else:
                    testcase.fail(
                        "User '%s' gets case '%s' "
                        "but shouldn't:%s" % (user.username, case_id, extra_info())
                    )
        if not n and should_have:
            testcase.fail("Block for case_id '%s' doesn't appear in ota restore for user '%s':%s"
                          % (case_id, user.username, extra_info()))

        return match

    matches = [check_block(case_block) for case_block in case_blocks]
    return restore_config, matches[0] if return_single else matches


def post_util(create=False, case_id=None, user_id=None, owner_id=None,
              case_type=None, version=V2, form_extras=None, close=False,
              **kwargs):

    uid = lambda: uuid.uuid4().hex
    case_id = case_id or uid()
    block = CaseBlock(create=create,
                      case_id=case_id,
                      user_id=user_id or uid(),
                      owner_id=owner_id or uid(),
                      case_type=case_type or 'test',
                      version=version,
                      update=kwargs,
                      close=close).as_xml()
    form_extras = form_extras or {}
    post_case_blocks([block], form_extras)
    return case_id


def _delete_all(db, viewname):
    deleted = set()
    for row in db.view(viewname, reduce=False):
        doc_id = row['id']
        if id not in deleted:
            try:
                safe_delete(db, doc_id)
                deleted.add(doc_id)
            except ResourceNotFound:
                pass


def delete_all_cases():
    assert settings.UNIT_TESTING
    _delete_all(CommCareCase.get_db(), 'case/get_lite')


def delete_all_xforms():
    assert settings.UNIT_TESTING
    _delete_all(XFormInstance.get_db(), 'couchforms/all_submissions_by_domain')


def delete_all_sync_logs():
    assert settings.UNIT_TESTING
    _delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')
