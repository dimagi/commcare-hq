from datetime import datetime, timedelta
import uuid
import os
import hashlib
from django.template import Template, Context

from django.test import TestCase
import lxml
from django.core.files.uploadedfile import UploadedFile
from mock import patch

from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
from casexml.apps.case.xml import V2
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from couchforms.models import XFormInstance
from dimagi.utils.parsing import json_format_datetime
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import TestFileMixin


TEST_CASE_ID = "EOL9FIAKIQWOFXFOH0QAMWU64"
CREATE_XFORM_ID = "6RGAZTETE3Z2QC0PE2DKM88MO"
media_path = os.path.join(os.path.dirname(__file__), "data", "attachments")

MEDIA_FILES = {
    "fruity_file": os.path.join(media_path, "fruity.jpg"),  # first
    "dimagi_logo_file": os.path.join(media_path, "dimagi_logo.jpg"),
    "commcare_logo_file": os.path.join(media_path, "commcare-logo.png"),
    "globe_file": os.path.join(media_path, "globe.pdf"),
    "house_file": os.path.join(media_path, "house.jpg"),
}


class BaseCaseMultimediaTest(TestCase, TestFileMixin):

    file_path = ('data', 'multimedia')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.formdb = FormAccessors()
        FormProcessorTestUtils.delete_all_cases()
        FormProcessorTestUtils.delete_all_xforms()

    def _formatXForm(self, doc_id, raw_xml, attachment_block, date=None):
        if date is None:
            date = datetime.utcnow()
        final_xml = Template(raw_xml).render(Context({
            "attachments": attachment_block,
            "time_start": json_format_datetime(date - timedelta(minutes=4)),
            "time_end": json_format_datetime(date),
            "date_modified": json_format_datetime(date),
            "doc_id": doc_id
        }))
        return final_xml

    def _prepAttachments(self, new_attachments, removes=[]):
        """
        Returns:
            attachment_block - An XML representation of the attachment
            dict_attachments - A key-value dict where the key is the name and the value is a Stream of the
            attachment
        """
        attachment_block = ''.join([self._singleAttachBlock(x) for x in new_attachments] + [self._singleAttachRemoveBlock(x) for x in removes])
        dict_attachments = dict((MEDIA_FILES[attach_name], self._attachmentFileStream(attach_name)) for attach_name in new_attachments)
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

    def _do_submit(self, xml_data, dict_attachments, sync_token=None, date=None):
        """
        RequestFactory submitter - simulates direct submission to server directly (no need to call process case after fact)
        """
        response, form, cases = submit_form_locally(
            xml_data,
            TEST_DOMAIN_NAME,
            attachments=dict_attachments,
            last_sync_token=sync_token,
            received_on=date
        )
        attachments = form.attachments
        self.assertEqual(set(dict_attachments.keys()),
                         set(attachments.keys()))
        [case] = cases
        self.assertEqual(case.case_id, TEST_CASE_ID)

        return response, form, cases

    def _submit_and_verify(self, doc_id, xml_data, dict_attachments,
                           sync_token=None, date=None):
        response, form, cases = self._do_submit(xml_data, dict_attachments, sync_token, date=date)

        attachments = form.attachments
        self.assertEqual(len(dict_attachments), len(attachments))
        for k, vstream in dict_attachments.items():
            fileback = form.get_attachment(k)
            # rewind the pointer before comparing
            orig_attachment = vstream
            orig_attachment.seek(0)
            self.assertEqual(hashlib.md5(fileback).hexdigest(), hashlib.md5(orig_attachment.read()).hexdigest())
        return response, form, cases

    def _doCreateCaseWithMultimedia(self, attachments=['fruity_file']):
        xml_data = self.get_xml('multimedia_create')
        attachment_block, dict_attachments = self._prepAttachments(attachments)
        final_xml = self._formatXForm(CREATE_XFORM_ID, xml_data, attachment_block)
        return self._submit_and_verify(CREATE_XFORM_ID, final_xml, dict_attachments)

    def _doSubmitUpdateWithMultimedia(self, new_attachments=None, removes=None,
                                      sync_token=None, date=None):
        new_attachments = new_attachments if new_attachments is not None \
            else ['commcare_logo_file', 'dimagi_logo_file']
        removes = removes if removes is not None else ['fruity_file']
        attachment_block, dict_attachments = self._prepAttachments(new_attachments, removes=removes)
        raw_xform = self.get_xml('multimedia_update')
        doc_id = uuid.uuid4().hex
        final_xform = self._formatXForm(doc_id, raw_xform, attachment_block, date)
        return self._submit_and_verify(doc_id, final_xform, dict_attachments,
                                sync_token, date=date)


class CaseMultimediaTest(BaseCaseMultimediaTest):
    """
    Tests new attachments for cases and case properties
    Spec: https://github.com/dimagi/commcare/wiki/CaseAttachmentAPI
    """
    def testAttachInCreate(self):
        single_attach = 'fruity_file'
        _, xform, [case] = self._doCreateCaseWithMultimedia(attachments=[single_attach])

        self.assertEqual(1, len(case.case_attachments))
        self.assertTrue(single_attach in case.case_attachments)
        self.assertEqual(1, len(filter(lambda x: x['action_type'] == 'attachment', case.actions)))
        self.assertEqual(
            self._calc_file_hash(single_attach),
            hashlib.md5(case.get_attachment(single_attach)).hexdigest()
        )

    def testArchiveAfterAttach(self):
        single_attach = 'fruity_file'
        _, _, [case] = self._doCreateCaseWithMultimedia(attachments=[single_attach])

        for xform_id in case.xform_ids:
            form = self.formdb.get_form(xform_id)

            form.archive()
            form = self.formdb.get_form(xform_id)
            self.assertTrue(form.is_archived)

            form.unarchive()
            form = self.formdb.get_form(xform_id)
            self.assertFalse(form.is_archived)

    def testAttachRemoveSingle(self):
        _, _, [case] = self._doCreateCaseWithMultimedia()
        new_attachments = []
        removes = ['fruity_file']
        _, _, [case] = self._doSubmitUpdateWithMultimedia(new_attachments=new_attachments, removes=removes)

        self.assertEqual(0, len(case.case_attachments))
        attach_actions = filter(lambda x: x['action_type'] == 'attachment', case.actions)
        self.assertEqual(2, len(attach_actions))
        last_action = attach_actions[-1]
        self.assertEqual(sorted(removes), sorted(last_action['attachments'].keys()))

    def testAttachRemoveMultiple(self):
        _, _, [case] = self._doCreateCaseWithMultimedia()

        new_attachments = ['commcare_logo_file', 'dimagi_logo_file']
        removes = ['fruity_file']
        _, _, [case] = self._doSubmitUpdateWithMultimedia(new_attachments=new_attachments, removes=removes)

        self.assertEqual(sorted(new_attachments), sorted(case.case_attachments.keys()))
        attach_actions = filter(lambda x: x['action_type'] == 'attachment', case.actions)
        self.assertEqual(2, len(attach_actions))

    def testOTARestoreSingle(self):
        _, _, [case] = self._doCreateCaseWithMultimedia()
        restore_attachments = ['fruity_file']
        self._validateOTARestore(case.case_id, restore_attachments)

    def testOTARestoreMultiple(self):
        _, _, [case] = self._doCreateCaseWithMultimedia()
        restore_attachments = ['commcare_logo_file', 'dimagi_logo_file']
        removes = ['fruity_file']
        _, _, [case] = self._doSubmitUpdateWithMultimedia(new_attachments=restore_attachments, removes=removes)

        self._validateOTARestore(case.case_id, restore_attachments)

    def _validateOTARestore(self, case_id, restore_attachments):
        case_xml = CaseAccessors().get_case(case_id).to_xml(V2)
        root_node = lxml.etree.fromstring(case_xml)
        attaches = root_node.find('{http://commcarehq.org/case/transaction/v2}attachment')
        self.assertEqual(len(restore_attachments), len(attaches))

        for attach in attaches:
            url = attach.values()[1]
            case_id = url.split('/')[-2]
            attach_key_from_url = url.split('/')[-1]
            tag = attach.tag
            clean_tag = tag.replace('{http://commcarehq.org/case/transaction/v2}', '')
            self.assertEqual(clean_tag, attach_key_from_url)
            self.assertEqual(case_id, TEST_CASE_ID)
            self.assertIn(attach_key_from_url, restore_attachments)
            restore_attachments.remove(clean_tag)

        self.assertEqual(0, len(restore_attachments))

    def testAttachInUpdate(self):
        new_attachments = ['commcare_logo_file', 'dimagi_logo_file']

        _, _, _ = self._doCreateCaseWithMultimedia()
        _, _, [case] = self._doSubmitUpdateWithMultimedia(new_attachments=new_attachments, removes=[])

        # 1 plus the 2 we had
        self.assertEqual(len(new_attachments) + 1, len(case.case_attachments))
        attach_actions = filter(lambda x: x['action_type'] == 'attachment', case.actions)
        self.assertEqual(2, len(attach_actions))
        last_action = attach_actions[-1]
        self.assertEqual(sorted(new_attachments), sorted(last_action['attachments'].keys()))

        for attach_name in new_attachments:
            self.assertTrue(attach_name in case.case_attachments)
            self.assertEqual(
                self._calc_file_hash(attach_name),
                hashlib.md5(case.get_attachment(attach_name)).hexdigest()
            )

    def testUpdateWithNoNewAttachment(self):
        _, _, [case] = self._doCreateCaseWithMultimedia()
        bulk_save = XFormInstance.get_db().bulk_save
        bulk_save_attachments = []

        # pull out and record attachments to docs being bulk saved
        def new_bulk_save(docs, *args, **kwargs):
            for doc in docs:
                if doc['_id'] == TEST_CASE_ID:
                    bulk_save_attachments.append(doc['_attachments'])
            bulk_save(docs, *args, **kwargs)

        self._doSubmitUpdateWithMultimedia(
            new_attachments=[], removes=[])

        with patch('couchforms.models.XFormInstance._db.bulk_save', new_bulk_save):
            # submit from the 2 min in the past to trigger a rebuild
            self._doSubmitUpdateWithMultimedia(
                new_attachments=[], removes=[],
                date=datetime.utcnow() - timedelta(minutes=2))

        # make sure there's exactly one bulk save recorded
        self.assertEqual(len(bulk_save_attachments), 1)
        # make sure none of the attachments were re-saved in rebuild
        self.assertEqual(
            [key for key, value in bulk_save_attachments[0].items()
             if value.get('data')], [])

    def test_sync_log_invalidation_bug(self):
        sync_log = FormProcessorInterface().sync_log_model(
            user_id='6dac4940-913e-11e0-9d4b-005056aa7fb5'
        )
        sync_log.save()
        _, _, [case] = self._doCreateCaseWithMultimedia()

        # this used to fail before we fixed http://manage.dimagi.com/default.asp?158373
        self._doSubmitUpdateWithMultimedia(new_attachments=['commcare_logo_file'], removes=[],
                                           sync_token=sync_log._id)
        FormProcessorTestUtils.delete_all_sync_logs()
