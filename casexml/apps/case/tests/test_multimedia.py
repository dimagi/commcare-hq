from datetime import datetime, timedelta
import time
import uuid
from django.test import TestCase
import os
import ipdb
import lxml
import simplejson
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases
from django.core.files.uploadedfile import UploadedFile
from couchforms.models import XFormInstance
import hashlib

TEST_CASE_ID = "EOL9FIAKIQWOFXFOH0QAMWU64"
CREATE_XFORM_ID = "6RGAZTETE3Z2QC0PE2DKM88MO"
media_path = os.path.join(os.path.dirname(__file__), "data", "attachments")

MEDIA_FILES = {
    "fruity": os.path.join(media_path, "fruity.jpg"), #first

    "dimagi_logo": os.path.join(media_path, "dimagi_logo.jpg"),
    "commcare_logo": os.path.join(media_path, "commcare-logo.png"),
    "globe": os.path.join(media_path, "globe.pdf"),
    "house": os.path.join(media_path, "house.jpg"),

}


class CaseMultimediaTest(TestCase):
    """
    Tests new attachments for cases and case properties
    Spec: https://bitbucket.org/commcare/commcare/wiki/CaseAttachmentAPI
    """

    def setUp(self):
        for item in CommCareCase.view("case/by_user", include_docs=True, reduce=False).all():
            print "delete cases!"
            item.delete()
        for item in XFormInstance.view("couchforms/by_xmlns", include_docs=True, reduce=False).all():
            print "delete xforms!"
            item.delete()
        print "finish setUp, all deleted"

    def _getXFormString(self, filename):
        file_path = os.path.join(os.path.dirname(__file__), "data", "multimedia", filename)
        with open(file_path, "rb") as f:
            xml_data = f.read()
        return xml_data

    def _formatXForm(self, raw_xml, attachment_block, doc_id=None):
        final_xml = raw_xml % ({
                                   "attachments": attachment_block,
                                   "time_start": (
                                       datetime.utcnow() - timedelta(minutes=4)).strftime(
                                       '%Y-%m-%dT%H:%M:%SZ'),
                                   "time_end": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                                   "date_modified": datetime.utcnow().strftime(
                                       '%Y-%m-%dT%H:%M:%SZ'),
                                   "doc_id": uuid.uuid4().hex if doc_id is None else doc_id
                               })
        return final_xml

    def _prepAttachments(self, new_attachments, removes=[]):
        attachment_block = ''.join([self._singleAttachBlock(x) for x in new_attachments] + [self._singleAttachRemoveBlock(x) for x in removes])
        dict_attachments = dict((attach_name, self._attachmentFileStream(attach_name)) for attach_name in new_attachments)
        return attachment_block, dict_attachments

    def _singleAttachBlock(self, key):
        return '<n0:%s src="%s" from="local"/>' % (key, MEDIA_FILES[key])

    def _singleAttachRemoveBlock(self, key):
        return '<n0:%s />' % key

    def _attachmentFileStream(self, key):
        attachment_path = MEDIA_FILES[key]
        attachment = open(attachment_path, 'rb')
        uf = UploadedFile(attachment, key)
        return uf

    def _calc_file_hash(self, key):
        with open(MEDIA_FILES[key], 'rb') as attach:
            return hashlib.md5(attach.read()).hexdigest()

    def _submit_and_verify(self, xml_data, dict_attachments):
        form = post_xform_to_couch(xml_data, attachments=dict_attachments)
        self.assertEqual(len(dict_attachments), len(form.attachments))
        for k, vstream in dict_attachments.items():
            fileback = form.fetch_attachment(k)
            # rewind the pointer before comparing
            orig_attachment = vstream
            orig_attachment.seek(0)
            self.assertEqual(hashlib.md5(fileback).hexdigest(), hashlib.md5(orig_attachment.read()).hexdigest())
        process_cases(sender="testharness", xform=form)
        return form

    def testAttachInCreate(self):
        print "testAttachInCreate"
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))

        xml_data = self._getXFormString('multimedia_create.xml')

        single_attach = 'fruity'
        attachment_block, dict_attachments = self._prepAttachments([single_attach])
        final_xml = self._formatXForm(xml_data, attachment_block, doc_id=CREATE_XFORM_ID)

        form = self._submit_and_verify(final_xml, dict_attachments)
        case = CommCareCase.get(TEST_CASE_ID)
        print "#### Load from DB"
        #print simplejson.dumps(case.to_json(), indent=4)
        self.assertEqual(1, len(case.case_attachments))
        self.assertTrue(single_attach in case.case_attachments)
        self.assertEqual(1, len(filter(lambda x: x['action_type'] == 'attachment', case.actions)))
        self.assertEqual(self._calc_file_hash(single_attach), hashlib.md5(case.get_attachment(single_attach)).hexdigest())

    def testAttachRemoveSingle(self):
        self.testAttachInCreate()
        new_attachments = []
        removes = ['fruity']
        attachment_block, dict_attachments = self._prepAttachments(new_attachments, removes=removes)

        raw_xform = self._getXFormString('multimedia_update.xml')
        final_xform = self._formatXForm(raw_xform, attachment_block)

        form = self._submit_and_verify(final_xform, {})
        case = CommCareCase.get(TEST_CASE_ID)
        print "#### testAttachInUpdate Load from DB"
        #print simplejson.dumps(case.to_json(), indent=4)
        print "_attachments: %s" % case['_attachments']

        #1 plus the 2 we had
        print case.case_attachments
        self.assertEqual(0, len(case.case_attachments))
        self.assertIsNone(case._attachments)
        attach_actions = filter(lambda x: x['action_type'] == 'attachment', case.actions)
        self.assertEqual(2, len(attach_actions))
        last_action = attach_actions[-1]
        self.assertEqual(sorted(removes), sorted(last_action['attachments'].keys()))

    def testAttachRemoveMultiple(self):
        self.testAttachInCreate()
        new_attachments = ['commcare_logo', 'dimagi_logo']
        removes = ['fruity']
        attachment_block, dict_attachments = self._prepAttachments(new_attachments, removes=removes)

        raw_xform = self._getXFormString('multimedia_update.xml')
        final_xform = self._formatXForm(raw_xform, attachment_block)

        form = self._submit_and_verify(final_xform, dict_attachments)
        case = CommCareCase.get(TEST_CASE_ID)
        print "#### testAttachInUpdate Load from DB"
        #print simplejson.dumps(case.to_json(), indent=4)
        print "_attachments: %s" % case['_attachments']

        #1 plus the 2 we had
        print case.case_attachments
        self.assertEqual(2, len(case.case_attachments))
        self.assertEqual(2, len(case._attachments))
        attach_actions = filter(lambda x: x['action_type'] == 'attachment', case.actions)
        self.assertEqual(2, len(attach_actions))
        last_action = attach_actions[-1]
        self.assertEqual(sorted(new_attachments), sorted(case._attachments.keys()))

    def testOTARestoreSingle(self):
        print "testOTARestoreSingle"
        self.testAttachInCreate()
        case = CommCareCase.get(TEST_CASE_ID)
        case_xml = case.to_xml(V2)
        root_node = lxml.etree.fromstring(case_xml)
        output = lxml.etree.tostring(root_node, pretty_print=True)
        print output


    def testAttachInUpdate(self):
        self.testAttachInCreate()
        new_attachments = ['commcare_logo', 'dimagi_logo']
        attachment_block, dict_attachments = self._prepAttachments(new_attachments)

        xml_data = self._getXFormString('multimedia_update.xml')
        final_xform = self._formatXForm(xml_data, attachment_block)
        form = self._submit_and_verify(final_xform, dict_attachments)
        case = CommCareCase.get(TEST_CASE_ID)
        print "#### testAttachInUpdate Load from DB"
        #print simplejson.dumps(case.to_json(), indent=4)
        print "_attachments: %s" % case['_attachments'].keys()


        #1 plus the 2 we had
        self.assertEqual(len(new_attachments)+1, len(case.case_attachments))
        attach_actions = filter(lambda x: x['action_type'] == 'attachment', case.actions)
        self.assertEqual(2, len(attach_actions))
        last_action = attach_actions[-1]
        self.assertEqual(sorted(new_attachments), sorted(last_action['attachments'].keys()))

        for attach_name in new_attachments:
            self.assertTrue(attach_name in case.case_attachments)
            self.assertEqual(self._calc_file_hash(attach_name), hashlib.md5(case.get_attachment(attach_name)).hexdigest())

