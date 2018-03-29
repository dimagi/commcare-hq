from __future__ import absolute_import
from __future__ import unicode_literals
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from xml.etree import cElementTree as ElementTree
from casexml.apps.phone.restore_caching import RestorePayloadPathCache
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import unit_testing_only

from dimagi.utils.dates import utcnow_sans_milliseconds
from lxml import etree

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V1, V2, NS_VERSION_MAP
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.restore import RestoreConfig, RestoreParams
from six.moves import range


TEST_DOMAIN_NAME = 'test-domain'


class _RestoreCaseBlock(object):
    """
    Little shim class for working with XML case blocks in a restore payload

    NOTE the recommended way to inspect case restore payloads is to
    use <MockDevice>.sync().cases, so don't use this in tests.
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
    updated_xml, uid, case_id = _replace_ids_in_xform_xml(
        xml_data,
        case_id_override=case_id_override,
    )

    domain = domain or 'test-domain'
    result = submit_form_locally(updated_xml, domain=domain)
    test_class.assertLessEqual(starttime, result.case.server_modified_on)
    test_class.assertGreaterEqual(datetime.utcnow(), result.case.server_modified_on)
    test_class.assertEqual(case_id, result.case.case_id)
    return result.xform, result.case


def _replace_ids_in_xform_xml(xml_data, case_id_override=None):
    # from our test forms, replace the UIDs so we don't get id conflicts
    uid, case_id = (uuid.uuid4().hex for i in range(2))

    if case_id_override:
        case_id = case_id_override

    xml_data = xml_data.replace("REPLACE_UID", uid)
    xml_data = xml_data.replace("REPLACE_CASEID", case_id)
    return xml_data, uid, case_id


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


def get_case_xmlns(version):
    return NS_VERSION_MAP.get(version, 'http://openrosa.org/http/response')


def extract_caseblocks_from_xml(payload_string, version=V2):
    parsed_payload = ElementTree.fromstring(payload_string)
    xml_blocks = parsed_payload.findall('{{{0}}}case'.format(get_case_xmlns(version)))
    return [_RestoreCaseBlock(b, version) for b in xml_blocks]


@contextmanager
def _cached_restore(testcase, user, restore_id="", version=V2,
                   purge_restore_cache=False):
    """DEPRECATED use <MockDevice>.sync().cases"""
    assert not hasattr(testcase, 'restore_config'), testcase
    assert not hasattr(testcase, 'payload_string'), testcase

    if restore_id and purge_restore_cache:
        RestorePayloadPathCache(
            domain=user.domain,
            user_id=user.user_id,
            sync_log_id=restore_id,
            device_id=None,
        ).invalidate()

    testcase.restore_config = RestoreConfig(
        project=user.project,
        restore_user=user, params=RestoreParams(restore_id, version=version),
        **getattr(testcase, 'restore_options', {})
    )
    testcase.payload_string = testcase.restore_config.get_payload().as_string()
    try:
        yield
    finally:
        del testcase.restore_config, testcase.payload_string


def deprecated_check_user_has_case(testcase, user, case_blocks, should_have=True,
                        line_by_line=True, restore_id="", version=V2,
                        purge_restore_cache=False, return_single=False):
    """DEPRECATED use <MockDevice>.sync().cases"""

    try:
        restore_config = testcase.restore_config
        payload_string = testcase.payload_string
    except AttributeError:
        with _cached_restore(testcase, user, restore_id, version, purge_restore_cache):
            restore_config = testcase.restore_config
            payload_string = testcase.payload_string

    return _check_payload_has_cases(
        testcase=testcase,
        payload_string=payload_string,
        username=user.username,
        case_blocks=case_blocks,
        should_have=should_have,
        line_by_line=line_by_line,
        version=version,
        return_single=return_single,
        restore_config=restore_config,
    )


def _check_payload_has_cases(testcase, payload_string, username, case_blocks, should_have=True,
                            line_by_line=True, version=V2, return_single=False, restore_config=None):
    """DEPRECATED use <MockDevice>.sync().cases"""

    if not isinstance(case_blocks, list):
        case_blocks = [case_blocks]
        return_single = True

    XMLNS = NS_VERSION_MAP.get(version, 'http://openrosa.org/http/response')
    blocks_from_restore = extract_caseblocks_from_xml(payload_string, version)

    def check_block(case_block):
        case_block.set('xmlns', XMLNS)
        case_block = _RestoreCaseBlock(ElementTree.fromstring(ElementTree.tostring(case_block)), version=version)
        case_id = case_block.get_case_id()
        n = 0

        def extra_info():
            return "\n%s\n%s" % (case_block.to_string(), [b.to_string() for b in blocks_from_restore])

        match = None
        for block in blocks_from_restore:
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
                            " in ota restore for user '%s':%s" % (case_id, username, extra_info())
                        )
                else:
                    testcase.fail(
                        "User '%s' gets case '%s' "
                        "but shouldn't:%s" % (username, case_id, extra_info())
                    )
        if not n and should_have:
            testcase.fail("Block for case_id '%s' doesn't appear in ota restore for user '%s':%s"
                          % (case_id, username, extra_info()))

        return match

    matches = [check_block(case_block) for case_block in case_blocks]
    return restore_config, matches[0] if return_single else matches


@unit_testing_only
def delete_all_cases():
    FormProcessorTestUtils.delete_all_cases()


@unit_testing_only
def delete_all_xforms():
    FormProcessorTestUtils.delete_all_xforms()


@unit_testing_only
def delete_all_sync_logs():
    FormProcessorTestUtils.delete_all_sync_logs()


@unit_testing_only
def delete_all_ledgers():
    FormProcessorTestUtils.delete_all_ledgers()
