from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
import uuid
import os
import hashlib

from django.conf import settings
from django.template import Template, Context

from django.test import TestCase
import lxml
from django.core.files.uploadedfile import UploadedFile
from mock import patch

from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
from casexml.apps.case.xml import V2
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.blobs import get_blob_db
from corehq.blobs.tests.util import TemporaryS3BlobDB
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from couchforms.models import XFormInstance
from dimagi.utils.parsing import json_format_datetime
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.util.test_utils import TestFileMixin, trap_extra_setup, flag_enabled
from io import open

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
        super(BaseCaseMultimediaTest, self).setUp()
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
        return NoClose(UploadedFile(attachment, key))

    def _calc_file_hash(self, key):
        with open(MEDIA_FILES[key], 'rb') as attach:
            return hashlib.md5(attach.read()).hexdigest()

    def _do_submit(self, xml_data, dict_attachments, sync_token=None, date=None):
        """
        RequestFactory submitter - simulates direct submission to server
        directly (no need to call process case after fact)
        """
        with flag_enabled('MM_CASE_PROPERTIES'):
            result = submit_form_locally(
                xml_data,
                TEST_DOMAIN_NAME,
                attachments=dict_attachments,
                last_sync_token=sync_token,
                received_on=date
            )
        attachments = result.xform.attachments
        self.assertEqual(set(dict_attachments.keys()),
                         set(attachments.keys()))
        self.assertEqual(result.case.case_id, TEST_CASE_ID)

        return result.response, result.xform, result.cases

    def _submit_and_verify(self, doc_id, xml_data, dict_attachments,
                           sync_token=None, date=None):
        response, form, [case] = self._do_submit(xml_data, dict_attachments, sync_token, date=date)

        attachments = form.attachments
        self.assertEqual(len(dict_attachments), len(attachments))
        for k, vstream in dict_attachments.items():
            fileback = form.get_attachment(k)
            # rewind the pointer before comparing
            orig_attachment = vstream
            orig_attachment.seek(0)
            self.assertEqual(hashlib.md5(fileback).hexdigest(), hashlib.md5(orig_attachment.read()).hexdigest())

        case = CaseAccessors(TEST_DOMAIN_NAME).get_case(case.case_id)  # re-fetch case
        return form, case

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


class CaseMultimediaTestCouch(BaseCaseMultimediaTest):

    def testUpdateWithNoNewAttachment(self):
        _, case = self._doCreateCaseWithMultimedia()
        bulk_save = XFormInstance.get_db().bulk_save
        bulk_save_attachments = []

        # pull out and record attachments to docs being bulk saved
        def new_bulk_save(docs, *args, **kwargs):
            for doc in docs:
                if doc['_id'] == TEST_CASE_ID:
                    bulk_save_attachments.append(doc._deferred_blobs)
            bulk_save(docs, *args, **kwargs)

        self._doSubmitUpdateWithMultimedia(
            new_attachments=[], removes=[])

        with patch('couchforms.models.XFormInstance._db.bulk_save', new_bulk_save):
            # submit from the 2 min in the past to trigger a rebuild
            self._doSubmitUpdateWithMultimedia(
                new_attachments=[], removes=[],
                date=datetime.utcnow() - timedelta(minutes=2))

        # make sure there's exactly one bulk save recorded
        # and none of the attachments were re-saved in rebuild
        self.assertEqual(bulk_save_attachments, [{}])


class CaseMultimediaTest(BaseCaseMultimediaTest):
    """
    Tests new attachments for cases and case properties
    Spec: https://github.com/dimagi/commcare/wiki/CaseAttachmentAPI
    """
    def testAttachInCreate(self):
        single_attach = 'fruity_file'
        xform, case = self._doCreateCaseWithMultimedia(attachments=[single_attach])

        self.assertEqual(1, len(case.case_attachments))
        self.assertTrue(single_attach in case.case_attachments)
        self.assertEqual(
            self._calc_file_hash(single_attach),
            hashlib.md5(case.get_attachment(single_attach)).hexdigest()
        )
        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(1, len([x for x in case.actions if x['action_type'] == 'attachment']))

    def testArchiveAfterAttach(self):
        single_attach = 'fruity_file'
        xform, case = self._doCreateCaseWithMultimedia(attachments=[single_attach])

        for xform_id in case.xform_ids:
            form = self.formdb.get_form(xform_id)

            form.archive()
            form = self.formdb.get_form(xform_id)
            self.assertTrue(form.is_archived)

            form.unarchive()
            form = self.formdb.get_form(xform_id)
            self.assertFalse(form.is_archived)

    def testAttachRemoveSingle(self):
        _, case = self._doCreateCaseWithMultimedia()
        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            attachment_sql = case.case_attachments['fruity_file']
            with attachment_sql.open() as content:
                self.assertTrue(content.read(1))

        new_attachments = []
        removes = ['fruity_file']
        _, case = self._doSubmitUpdateWithMultimedia(new_attachments=new_attachments, removes=removes)

        self.assertEqual(0, len(case.case_attachments))

        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(case.case_attachments, {})
        else:
            attach_actions = [x for x in case.actions if x['action_type'] == 'attachment']
            self.assertEqual(2, len(attach_actions))
            last_action = attach_actions[-1]
            self.assertEqual(sorted(removes), sorted(last_action['attachments'].keys()))

    def testAttachRemoveMultiple(self):
        self._doCreateCaseWithMultimedia()

        new_attachments = ['commcare_logo_file', 'dimagi_logo_file']
        removes = ['fruity_file']
        _, case = self._doSubmitUpdateWithMultimedia(new_attachments=new_attachments, removes=removes)

        self.assertEqual(sorted(new_attachments), sorted(case.case_attachments.keys()))

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            attach_actions = [x for x in case.actions if x['action_type'] == 'attachment']
            self.assertEqual(2, len(attach_actions))

    @flag_enabled('MM_CASE_PROPERTIES')
    def testOTARestoreSingle(self):
        _, case = self._doCreateCaseWithMultimedia()
        restore_attachments = ['fruity_file']
        self._validateOTARestore(case.case_id, restore_attachments)

    @flag_enabled('MM_CASE_PROPERTIES')
    def testOTARestoreMultiple(self):
        _, case = self._doCreateCaseWithMultimedia()
        restore_attachments = ['commcare_logo_file', 'dimagi_logo_file']
        removes = ['fruity_file']
        _, case = self._doSubmitUpdateWithMultimedia(new_attachments=restore_attachments, removes=removes)

        self._validateOTARestore(case.case_id, restore_attachments)

    def _validateOTARestore(self, case_id, restore_attachments):
        case_xml = CaseAccessors().get_case(case_id).to_xml(V2)
        root_node = lxml.etree.fromstring(case_xml)
        attaches = root_node.find('{http://commcarehq.org/case/transaction/v2}attachment')
        self.assertEqual(len(restore_attachments), len(attaches))

        for attach in attaches:
            url = list(attach.values())[1]
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

        self._doCreateCaseWithMultimedia()
        _, case = self._doSubmitUpdateWithMultimedia(new_attachments=new_attachments, removes=[])

        # 1 plus the 2 we had
        self.assertEqual(len(new_attachments) + 1, len(case.case_attachments))
        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            attach_actions = [x for x in case.actions if x['action_type'] == 'attachment']
            self.assertEqual(2, len(attach_actions))
            last_action = attach_actions[-1]
            self.assertEqual(sorted(new_attachments), sorted(last_action['attachments'].keys()))

        for attach_name in new_attachments:
            self.assertTrue(attach_name in case.case_attachments)
            self.assertEqual(
                self._calc_file_hash(attach_name),
                hashlib.md5(case.get_attachment(attach_name)).hexdigest()
            )

    def test_sync_log_invalidation_bug(self):
        sync_log = FormProcessorInterface().sync_log_model(
            user_id='6dac4940-913e-11e0-9d4b-005056aa7fb5'
        )
        sync_log.save()
        self.addCleanup(FormProcessorTestUtils.delete_all_sync_logs)

        _, case = self._doCreateCaseWithMultimedia()

        # this used to fail before we fixed http://manage.dimagi.com/default.asp?158373
        self._doSubmitUpdateWithMultimedia(new_attachments=['commcare_logo_file'], removes=[],
                                           sync_token=sync_log._id)


@use_sql_backend
class CaseMultimediaTestSQL(CaseMultimediaTest):
    pass


class CaseMultimediaS3DBTest(BaseCaseMultimediaTest):
    """
    Tests new attachments for cases and case properties
    Spec: https://github.com/dimagi/commcare/wiki/CaseAttachmentAPI
    """

    def setUp(self):
        super(CaseMultimediaS3DBTest, self).setUp()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS

        self.s3db = TemporaryS3BlobDB(config)
        assert get_blob_db() is self.s3db, (get_blob_db(), self.s3db)

    def tearDown(self):
        self.s3db.close()
        super(CaseMultimediaS3DBTest, self).tearDown()

    def test_case_attachment(self):
        single_attach = 'fruity_file'
        xform, case = self._doCreateCaseWithMultimedia(attachments=[single_attach])

        self.assertEqual(1, len(case.case_attachments))
        self.assertTrue(single_attach in case.case_attachments)
        self.assertEqual(
            self._calc_file_hash(single_attach),
            hashlib.md5(case.get_attachment(single_attach)).hexdigest()
        )


@use_sql_backend
class CaseMultimediaS3DBTestSQL(CaseMultimediaS3DBTest):
    pass


class NoClose(object):
    """HACK file object with no-op `close()` to avoid close by S3Transfer

    https://github.com/boto/s3transfer/issues/80
    """

    def __init__(self, fileobj):
        self.fileobj = fileobj

    def __getattr__(self, name):
        return getattr(self.fileobj, name)

    def close(self):
        pass
