import os
import uuid

from datetime import datetime, timedelta
from xml.etree import ElementTree

from couchforms.util import post_xform_to_couch
from couchforms.models import XFormInstance

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import process_cases
from dimagi.utils.dates import utcnow_sans_milliseconds
from lxml import etree
from dimagi.utils.parsing import json_format_datetime

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

class CaseBlockError(Exception):
    pass

class CaseBlock(dict):
    undefined = object()
    def __init__(self, case_id, date_modified=None,
            create=undefined,
                create__case_type_id=undefined,
                create__case_name=undefined,
                create__external_id=undefined,
                create__user_id=undefined,
            update=undefined,
                update__case_type_id=undefined,
                update__case_name=undefined,
                update__date_opened=undefined,
                update__owner_id=undefined, # just for kicks
            close=undefined,
            # referrals currently not supported
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
        
        """
        super(CaseBlock, self).__init__()
        self.update({
            'case_id': case_id,
            'date_modified': date_modified or datetime.utcnow(),
        })
        tmp_create = {} if create is CaseBlock.undefined else create # maybe one of create__* is passed in
        tmp_update = {} if update is CaseBlock.undefined else update # maybe one of update__* is passed in

        for key in ('case_type_id', 'case_name', 'external_id', 'user_id'):
            value = locals()['create__%s' % key]
            if value is not CaseBlock.undefined:
                tmp_create[key] = value

        for key in ('case_type_id', 'case_name', 'date_opened', 'owner_id'):
            value = locals()['update__%s' % key]
            if value is not CaseBlock.undefined:
                tmp_update[key] = value

        if create is not CaseBlock.undefined or tmp_create:
            for required_key in 'case_type_id', 'case_name', 'external_id':
                if not tmp_create.has_key(required_key):
                    raise CaseBlockError("Attempt to make <create/> block without <%s/>" % required_key)
            self['create'] = tmp_create
            
        if update is not CaseBlock.undefined or tmp_update:
            self['update'] = tmp_update
            
        if close is not CaseBlock.undefined:
            self['closed'] = {}

    def as_xml(self, format_datetime=None):
        format_datetime = format_datetime or json_format_datetime
        case = ElementTree.Element('case')
        order = ['case_id', 'date_modified', 'create', 'update', 'close',
                 'case_type_id', 'user_id', 'case_name', 'external_id', 'date_opened', 'owner_id']
        def sort_key(item):
            word, _ = item
            try:
                i = order.index(word)
                return 0, i
            except ValueError:
                return 1, word

        def dict_to_xml(block, dct):
            for (key, value) in sorted(dct.items(), key=sort_key):
                elem = ElementTree.Element(key)
                block.append(elem)
                if isinstance(value, dict):
                    dict_to_xml(elem, value)
                elif isinstance(value, datetime):
                    elem.text = unicode(format_datetime(value))
                elif isinstance(value, basestring):
                    elem.text = unicode(value)
                else:
                    raise CaseBlockError("Can't transform to XML: %s; unexpected type." % value)
        dict_to_xml(case, self)
        return case