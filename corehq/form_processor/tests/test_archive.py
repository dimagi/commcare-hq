from datetime import datetime, timedelta
from django.test import TestCase
from couchforms.signals import xform_archived, xform_unarchived

from ..generic import GenericXFormInstance, GenericFormAttachment
from ..interfaces import FormProcessorInterface


class TestFormArchiving(TestCase):

    def testArchive(self):
        xform = FormProcessorInterface.create_from_generic(
            GenericXFormInstance(form={'foo': 'bar'}),
            GenericFormAttachment(name='form.xml', content='<data/>')
        )

        generic_xform = xform.to_generic()
        self.assertEqual("XFormInstance", generic_xform.doc_type)
        self.assertEqual(0, len(generic_xform.history))

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        FormProcessorInterface.archive_xform(xform, user='mr. librarian')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)

        xform = FormProcessorInterface.get_xform(generic_xform.id)
        self.assertEqual('XFormArchived', xform.to_generic().doc_type)

        [archival] = xform.to_generic().history
        self.assertTrue(lower_bound <= archival.date <= upper_bound)
        self.assertEqual('archive', archival.operation)
        self.assertEqual('mr. librarian', archival.user)

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        FormProcessorInterface.unarchive_xform(xform, user='mr. researcher')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)

        xform = FormProcessorInterface.get_xform(xform.to_generic().id)
        self.assertEqual('XFormInstance', xform.to_generic().doc_type)

        [archival, restoration] = xform.to_generic().history
        self.assertTrue(lower_bound <= restoration.date <= upper_bound)
        self.assertEqual('unarchive', restoration.operation)
        self.assertEqual('mr. researcher', restoration.user)

    def testSignal(self):
        global archive_counter, restore_counter
        archive_counter = 0
        restore_counter = 0

        def count_archive(**kwargs):
            global archive_counter
            archive_counter += 1

        def count_unarchive(**kwargs):
            global restore_counter
            restore_counter += 1

        xform_archived.connect(count_archive)
        xform_unarchived.connect(count_unarchive)

        xform = FormProcessorInterface.create_from_generic(
            GenericXFormInstance(form={'foo': 'bar'}),
            GenericFormAttachment(name='form.xml', content='<data/>')
        )

        self.assertEqual(0, archive_counter)
        self.assertEqual(0, restore_counter)

        FormProcessorInterface.archive_xform(xform)
        self.assertEqual(1, archive_counter)
        self.assertEqual(0, restore_counter)

        FormProcessorInterface.unarchive_xform(xform)
        self.assertEqual(1, archive_counter)
        self.assertEqual(1, restore_counter)
