from datetime import datetime, timedelta
from django.test import TestCase
from couchforms.models import XFormInstance, XFormArchived
from couchforms.signals import xform_archived, xform_unarchived
from couchforms import fetch_and_wrap_form


class TestFormArchiving(TestCase):

    def testArchive(self):
        form = XFormInstance(form={'foo': 'bar'})
        form.save()
        self.assertEqual("XFormInstance", form.doc_type)
        self.assertEqual(0, len(form.history))

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        form.archive(user='mr. librarian')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)
        form = fetch_and_wrap_form(form._id)
        self.assertEqual('XFormArchived', form.doc_type)
        self.assertTrue(isinstance(form, XFormArchived))

        [archival] = form.history
        self.assertTrue(lower_bound <= archival.date <= upper_bound)
        self.assertEqual('archive', archival.operation)
        self.assertEqual('mr. librarian', archival.user)

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        form.unarchive(user='mr. researcher')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)
        form = fetch_and_wrap_form(form._id)
        self.assertEqual('XFormInstance', form.doc_type)
        self.assertTrue(isinstance(form, XFormInstance))

        [archival, restoration] = form.history
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

        form = XFormInstance(form={'foo': 'bar'})
        form.save()
        self.assertEqual(0, archive_counter)
        self.assertEqual(0, restore_counter)

        form.archive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(0, restore_counter)

        form.unarchive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(1, restore_counter)

