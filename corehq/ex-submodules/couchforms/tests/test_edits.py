import os
from couchdbkit import ResourceNotFound, RequestFailed
from django.test import TestCase
from mock import MagicMock
from corehq.apps.receiverwrapper import submit_form_locally
from couchforms.models import XFormDeprecated, XFormInstance, \
    UnfinishedSubmissionStub
from couchforms.tests.testutils import post_xform_to_couch


class EditFormTest(TestCase):
    ID = '7H46J37FGH3'

    def tearDown(self):
        try:
            XFormInstance.get_db().delete_doc(self.ID)
        except ResourceNotFound:
            pass
        deprecated_xforms = XFormDeprecated.view(
            'couchforms/edits',
            include_docs=True,
        ).all()
        for form in deprecated_xforms:
            form.delete()

    def _get_files(self):
        first_file = os.path.join(os.path.dirname(__file__), "data", "duplicate.xml")
        edit_file = os.path.join(os.path.dirname(__file__), "data", "edit.xml")

        with open(first_file, "rb") as f:
            xml_data1 = f.read()
        with open(edit_file, "rb") as f:
            xml_data2 = f.read()

        return xml_data1, xml_data2

    def test_basic_edit(self):
        xml_data1, xml_data2 = self._get_files()

        docs = []

        doc = post_xform_to_couch(xml_data1)
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("", doc.form['vitals']['height'])
        self.assertEqual("other", doc.form['assessment']['categories'])
        doc.domain = 'test-domain'
        doc.save()

        doc = post_xform_to_couch(xml_data2, domain='test-domain')
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("100", doc.form['vitals']['height'])
        self.assertEqual("Edited Baby!", doc.form['assessment']['categories'])

        docs.append(doc)

        doc = XFormDeprecated.view('couchforms/edits', include_docs=True).first()
        self.assertEqual(self.ID, doc.orig_id)
        self.assertNotEqual(self.ID, doc.get_id)
        self.assertEqual(XFormDeprecated.__name__, doc.doc_type)
        self.assertEqual("", doc.form['vitals']['height'])
        self.assertEqual("other", doc.form['assessment']['categories'])

        self.assertEqual(XFormInstance.get_db().fetch_attachment(doc.get_id, 'form.xml'), xml_data1)
        self.assertEqual(XFormInstance.get_db().fetch_attachment(self.ID, 'form.xml'), xml_data2)

        for doc in docs:
            doc.delete()

    def test_broken_save(self):
        """
        Test that if the second form submission terminates unexpectedly
        and the main form isn't saved, then there are no side effects
        such as the original having been marked as deprecated.
        """

        class BorkDB(object):
            """context manager for making a db's bulk_save temporarily fail"""
            def __init__(self, db):
                self.old = {}
                self.db = db

            def __enter__(self):
                self.old['bulk_save'] = self.db.bulk_save
                self.db.bulk_save = MagicMock(name='bulk_save',
                                              side_effect=RequestFailed())

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.db.bulk_save = self.old['bulk_save']

        self.assertEqual(
            XFormInstance.view('couchforms/edits', key=self.ID).count(), 0)
        self.assertFalse(XFormInstance.get_db().doc_exist(self.ID))

        xml_data1, xml_data2 = self._get_files()

        submit_form_locally(xml_data1, 'test-domain')
        doc = XFormInstance.get(self.ID)
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual('test-domain', doc.domain)

        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            0
        )

        with BorkDB(XFormInstance.get_db()):
            with self.assertRaises(RequestFailed):
                submit_form_locally(xml_data2, 'test-domain')

        # it didn't go through, so make sure there are no edits still
        self.assertEqual(
            XFormInstance.view('couchforms/edits', key=self.ID).count(), 0)
        self.assertTrue(XFormInstance.get_db().doc_exist(self.ID))
        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID,
                                                    saved=False).count(),
            1
        )
        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            1
        )
