import os
import uuid

from datetime import datetime
from xml.etree import ElementTree
from casexml.apps.case.xml import V1, V2, NS_VERSION_MAP

from couchforms.util import post_xform_to_couch
from couchforms.models import XFormInstance

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import process_cases
from dimagi.utils.dates import utcnow_sans_milliseconds
from lxml import etree
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.phone.xml import date_to_xml_string

from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.case.util import post_case_blocks

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
        expected_lines = parsed_expected.split("\n")
        actual_lines = parsed_actual.split("\n")
        test_case.assertEqual(len(expected_lines), len(actual_lines), "Parsed xml files are different lengths\n" + 
                              "Expected: \n%s\nActual:\n%s" % (parsed_expected, parsed_actual)) 
        for i in range(len(expected_lines)):
            test_case.assertEqual(expected_lines[i], actual_lines[i])
            
    except AssertionError:
        import logging
        logging.error("Failure in xml comparison\nExpected:\n%s\nActual:\n%s" % (parsed_expected, parsed_actual))
        raise

class CaseBlockError(Exception):
    pass

class CaseBlock(dict):
    """
    Doctests:

    >>> NOW = datetime(year=2012, month=1, day=24)
    >>> FIVE_DAYS_FROM_NOW = datetime(year=2012, month=1, day=29)
    >>> CASE_ID = 'test-case-id'

    # Basic
    >>> ElementTree.tostring(CaseBlock(
    ...     case_id=CASE_ID,
    ...     date_opened=NOW,
    ...     date_modified=NOW,
    ... ).as_xml())
    '<case><case_id>test-case-id</case_id><date_modified>2012-01-24</date_modified><update><date_opened>2012-01-24</date_opened></update></case>'

    # Doesn't let you specify a keyword twice (here 'case_name')
    >>> try:
    ...     CaseBlock(
    ...         case_id=CASE_ID,
    ...         case_name='Johnny',
    ...         update={'case_name': 'Johnny'},
    ...     ).as_xml()
    ... except CaseBlockError, e:
    ...     print "%s" % e
    Key 'case_name' specified twice

    # The following is a BUG; should fail!! Should fix and change tests
    >>> ElementTree.tostring(CaseBlock(
    ...     case_id=CASE_ID,
    ...     date_opened=NOW,
    ...     date_modified=NOW,
    ...     update={
    ...         'date_opened': FIVE_DAYS_FROM_NOW,
    ...     },
    ... ).as_xml())
    '<case><case_id>test-case-id</case_id><date_modified>2012-01-24</date_modified><update><date_opened>2012-01-24</date_opened></update></case>'

    """
    undefined = object()
    def __init__(self,
            case_id,
            date_modified=None,
            user_id=undefined,
            owner_id=undefined,
            external_id=undefined,
            case_type=undefined,
            case_name=undefined,
            create=False,
            date_opened=undefined,
            update=None,
            close=False,
            # referrals currently not supported
            # V2 only
            index=None,
            version=V1,
            compatibility_mode=False,
        ):
        """
        From https://bitbucket.org/javarosa/javarosa/wiki/casexml

        <case>
            <case_id/>        <-- Exactly One: The id of the abstract case to be modified (even in the case of creation)
            <date_modified/>  <-- Exactly One: The date of this operation

            <create>         <-- At Most One: Create action
                <case_type_id/>             <-- Exactly One: The ID for the type of case represented
                <user_id/>                  <-- At Most One: The ID for a user who created the case
                <case_name/>                <-- Exactly One: A semantically meaningless but human readable name associated with the case
                <external_id/>              <-- Exactly One: The soft id associated with this record. Generally based on another system's id for this record.
            </create>

            <update/>         <-- At Most One: Updates data for the case
                <case_type_id/>             <-- At Most One: Modifies the Case Type for the case
                <case_name/>                <-- At Most One: A semantically meaningless but human readable name associated with the case
                <date_opened/>              <-- At Most One: Modifies the Date the case was opened
                <*/>                        <-- An Arbitrary Number: Creates or mutates a value identified by the key provided
            </update>

            <close/>          <-- At Most One: Closes the case
            
#            <referral>       <-- At Most One: Referral actions
#                <referral_id/>              <-- Exactly One: The unique ID. No two referrals should be open with both the same referral_id and referral_type
#                <followup_date/>            <-- At Most One: The due date for all followups referenced in this action
#                <open>
#                    <referral_types/>       <-- Exactly One: A space separated list of referral types which should be opened.
#                </open>
#                <update>
#                    <referral_type/>        <-- Exactly One: The referral type to be changed
#                    <date_closed/>          <-- At Most One: The date the referral was closed. If this element exists, the abstract referral matching the referral_id and referral_type should be closed.
#                </update>
#            </referral>
        </case>

        https://bitbucket.org/commcare/commcare/wiki/casexml20

        <case xmlns="http://commcarehq.org/case/transaction/v2" case_id="" user_id="" date_modified="" >
            <!-- user_id - At Most One: the GUID of the user responsible for this transaction -->
            <!-- case_id - Exactly One: The id of the abstract case to be modified (even in the case of creation) -->
            <!-- date_modified - Exactly One: The date and time of this operation -->
            <create>         <!-- At Most One: Create action -->
                <case_type/>             <!-- Exactly One: The ID for the type of case represented -->
                <owner_id/>                 <!-- At Most One: The GUID of the current owner of this case -->
                <case_name/>                <!-- Exactly One: A semantically meaningless but human readable name associated with the case -->
            </create>
            <update>         <!-- At Most One: Updates data for the case -->
                <case_type/>             <!-- At Most One: Modifies the Case Type for the case -->
                <case_name/>                <!-- At Most One: A semantically meaningless but human  readable name associated with the case -->
                <date_opened/>              <!-- At Most One: Modifies the Date the case was opened -->
                <owner_id/>                 <!-- At Most One: Modifies the owner of this case -->
                <*/>                        <-- An Arbitrary Number: Creates or mutates a value  identified by the key provided -->
            </update>
            <index/>          <!-- At Most One: Contains a set of referenced GUID's to other cases -->
            <close/>          <!-- At Most One: Closes the case -->
         </case>

        """
        super(CaseBlock, self).__init__()
        date_modified = date_modified or datetime.utcnow()
        update = update or {}
        index = index or {}

        self.XMLNS = NS_VERSION_MAP.get(version)

        if version == V1:
            self.VERSION = V1
            self.CASE_TYPE = "case_type_id"
        elif version == V2:
            self.VERSION = V2
            self.CASE_TYPE = "case_type"
        else:
            raise CaseBlockError("Case XML version must be %s or %s" % (V1, V2))

        if create:
            self['create'] = {}
            # make case_type
            case_type = "" if case_type is CaseBlock.undefined else case_type
            case_name = "" if case_name is CaseBlock.undefined else case_name
            if version == V2:
                owner_id = "" if owner_id is CaseBlock.undefined else owner_id
        self['update'] = update
        self['update'].update({
            'date_opened':                  date_opened
        })
        create_or_update = {
            self.CASE_TYPE:                 case_type,
            'case_name':                    case_name,
        }

        # what to do with case_id, date_modified, user_id, and owner_id, external_id
        if version == V1:
            self.update({
                'case_id':                  case_id, # V1
                'date_modified':            date_modified, # V1
            })
            if create:
                self['create'].update({
                    'user_id':              user_id, # V1
                })
            else:
                if not compatibility_mode and user_id is not CaseBlock.undefined:
                    CaseBlockError("CaseXML V1: You only set user_id when creating a case")
            self['update'].update({
                'owner_id':                 owner_id, # V1
            })
            create_or_update.update({
                'external_id':              external_id # V1
            })
        else:
            self.update({
                '_attrib': {
                    'case_id':              case_id, # V2
                    'date_modified':        date_modified, # V2
                    'user_id':              user_id, # V2
                    'xmlns':                self.XMLNS,
                }
            })
            create_or_update.update({
                'owner_id':                 owner_id, # V2
            })
            self['update'].update({
                'external_id':              external_id, # V2
            })


        # fail if user specifies both, say, case_name='Johnny' and update={'case_name': 'Johnny'}
        for key in create_or_update:
            if create_or_update[key] is not CaseBlock.undefined and self['update'].has_key(key):
                raise CaseBlockError("Key %r specified twice" % key)
                
        if create:
            self['create'].update(create_or_update)
        else:
            self['update'].update(create_or_update)

        
        if close:
            self['close'] = {}

        if not ['' for val in self['update'].values() if val is not CaseBlock.undefined]:
                self['update'] = CaseBlock.undefined
        if index and version == V2:
            self['index'] = {}
            for name, (case_type, case_id) in index.items():
                self['index'][name] = {
                    '_attrib': {
                        'case_type': case_type
                    },
                    '_text': case_id
                }
        
    def as_xml(self, format_datetime=date_to_xml_string):
        format_datetime = format_datetime or json_format_datetime
        case = ElementTree.Element('case')
        order = ['case_id', 'date_modified', 'create', 'update', 'close',
                 self.CASE_TYPE, 'user_id', 'case_name', 'external_id', 'date_opened', 'owner_id']
        def sort_key(item):
            word, _ = item
            try:
                i = order.index(word)
                return 0, i
            except ValueError:
                return 1, word

        def fmt(value):
            if isinstance(value, datetime):
                return unicode(format_datetime(value))
            elif isinstance(value, basestring):
                return unicode(value)
            else:
                raise CaseBlockError("Can't transform to XML: %s; unexpected type." % value)

        def dict_to_xml(block, dct):
            if dct.has_key('_attrib'):
                for (key, value) in dct['_attrib'].items():
                    if value is not CaseBlock.undefined:
                        block.set(key, fmt(value))
            if dct.has_key('_text'):
                block.text = unicode(dct['_text'])

            for (key, value) in sorted(dct.items(), key=sort_key):
                if value is not CaseBlock.undefined and not key.startswith('_'):
                    elem = ElementTree.Element(key)
                    block.append(elem)
                    if isinstance(value, dict):
                        dict_to_xml(elem, value)
                    else:
                        elem.text = fmt(value)
        dict_to_xml(case, self)
        return case
    
    
def check_user_has_case(testcase, user, case_block, should_have=True,
                        line_by_line=True, restore_id="", version=V1):
    XMLNS = NS_VERSION_MAP.get(version, 'http://openrosa.org/http/response')
    case_block.set('xmlns', XMLNS)
    case_block = ElementTree.fromstring(ElementTree.tostring(case_block))
    payload_string = generate_restore_payload(user, restore_id, version=version)
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
               case_type=None, version=V2, **kwargs):

    uid = lambda: uuid.uuid4().hex
    case_id = case_id or uid()
    block = CaseBlock(create=create,
                      case_id=case_id,
                      user_id=user_id or uid(),
                      owner_id=owner_id or uid(),
                      case_type=case_type or DEFAULT_TEST_TYPE,
                      version=version,
                      update=kwargs).as_xml()
    post_case_blocks([block])
    return case_id
