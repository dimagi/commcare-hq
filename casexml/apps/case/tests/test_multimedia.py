from datetime import datetime, timedelta
import time
import uuid
from django.test import TestCase
import os
import simplejson
from casexml.apps.case.models import CommCareCase
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases
from django.core.files.uploadedfile import UploadedFile
from couchforms.models import XFormInstance
import hashlib

TEST_CASE_ID = "EOL9FIAKIQWOFXFOH0QAMWU64"
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

    def _singleAttachBlock(self, key):
        return '<n0:%s src="%s" from="local"/>' % (key, MEDIA_FILES[key])

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
        return form

    def testAttachInCreate(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))

        file_path = os.path.join(os.path.dirname(__file__), "data", "multimedia", "multimedia_create.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        #hmmm, this could be tricky
        attach_name = "fruity"

        final_xml = xml_data % ({"attachments": self._singleAttachBlock(attach_name)})
        dict_attachments = {attach_name: self._attachmentFileStream(attach_name)}
        form = self._submit_and_verify(final_xml, dict_attachments)

        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get(TEST_CASE_ID)
        print "#### Load from DB"
        print simplejson.dumps(case.to_json(), indent=4)
        self.assertEqual(1, len(case.case_attachments))
        self.assertTrue(attach_name in case.case_attachments)
        self.assertEqual(1, len(filter(lambda x: x['action_type'] == 'attachment', case.actions)))
        self.assertEqual(self._calc_file_hash(attach_name), hashlib.md5(case.get_attachment(attach_name)).hexdigest())

    def testAttachInUpdate(self):
        self.testAttachInCreate()

        file_path = os.path.join(os.path.dirname(__file__), "data", "multimedia", "multimedia_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        new_attachments = ['commcare_logo', 'dimagi_logo']

        attachment_block = ''.join(self._singleAttachBlock(x) for x in new_attachments)
        final_xml = xml_data % ({
                                    "attachments": attachment_block,
                                    "time_start": (datetime.utcnow() - timedelta(minutes=4)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                    "time_end": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                                    "date_modified": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                                    "doc_id": uuid.uuid4().hex
                                })

        dict_attachments = dict((attach_name, self._attachmentFileStream(attach_name)) for attach_name in new_attachments)
        form = self._submit_and_verify(final_xml, dict_attachments)
        process_cases(sender="testharness", xform=form)
        time.sleep(2)
        case = CommCareCase.get(TEST_CASE_ID)
        print "#### testAttachInUpdate Load from DB"
        print simplejson.dumps(case.to_json(), indent=4)
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

