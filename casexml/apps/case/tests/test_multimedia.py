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
    "dimagi_logo": os.path.join(media_path, "dimagi_logo.jpg"),
    "commcare_logo": os.path.join(media_path, "commcare-logo.png"),
    "fruity": os.path.join(media_path, "fruity.jpg"),
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
            item.delete()
        for item in XFormInstance.view("couchforms/by_xmlns", include_docs=True, reduce=False).all():
            item.delete()

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
        self.assertEqual(1, len(case.attachments))
        self.assertTrue(attach_name in case.attachments)
        self.assertEqual(1, len(filter(lambda x: x['action_type'] == 'attachment', case.actions)))
        self.assertEqual(self._calc_file_hash(attach_name), hashlib.md5(case.get_attachment(attach_name)).hexdigest())

    def testAttachInUpdate(self):
        self.testAttachInCreate()

        file_path = os.path.join(os.path.dirname(__file__), "data", "multimedia", "multimedia_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        attach_name = "house.jpg"
        attachment_path = os.path.join(os.path.dirname(__file__), "data", "attachments", attach_name)
        with open(attachment_path, "rb") as attachment:
            uf = UploadedFile(attachment, attach_name)
            form = post_xform_to_couch(xml_data, {attach_name: uf})
            self.assertEqual(1, len(form.attachments))
            fileback = form.fetch_attachment(attach_name)
            # rewind the pointer before comparing
            attachment.seek(0)
            self.assertEqual(hashlib.md5(fileback).hexdigest(),
                             hashlib.md5(attachment.read()).hexdigest())


        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get(TEST_CASE_ID)
        #print simplejson.dumps(case.to_json(), indent=4)
        self.assertEqual(2, len(case.attachments))
        # self.assertEqual(form.get_id, case.attachments[1][0])
        # self.assertEqual(attach_name, case.attachments[1][1])

