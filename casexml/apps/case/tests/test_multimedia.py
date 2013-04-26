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

    def testAttachInCreate(self):
        # <n0:photo1 src="fruity.jpg" from="local"/>
        # <n0:photo2 src="house.jpg" from="local"/>
        #http://www.dimagi.com/wp-content/uploads/2010/07/TheVolcano3.mp4
        #http://www.dimagi.com/wp-content/uploads/2012/10/commcare-div2-pressrelease.png
        #http://www.dimagi.com/wp-content/uploads/2012/10/dimagi-div2-pressrelease.png

        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))

        file_path = os.path.join(os.path.dirname(__file__), "data", "multimedia", "multimedia_create.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        attach_name = "fruity.jpg"
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
        print simplejson.dumps(case.to_json(), indent=4)
        self.assertEqual(1, len(case.attachments))
        self.assertEqual(form.get_id, case.attachments[0][0])
        self.assertEqual(attach_name, case.attachments[0][1])


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
        print simplejson.dumps(case.to_json(), indent=4)
        self.assertEqual(2, len(case.attachments))
        self.assertEqual(form.get_id, case.attachments[1][0])
        self.assertEqual(attach_name, case.attachments[1][1])

