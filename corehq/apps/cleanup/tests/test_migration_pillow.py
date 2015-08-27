import os

from corehq.apps.domain.models import Domain
from couchdbkit import ResourceNotFound
from django.test import TestCase
from django.core import management
from django.conf import settings

from couchforms.models import XFormInstanceDevicelog, XFormInstance

from ..pillows import DevicelogMigrationPillow

DEVICELOG_XMLNS = 'http://code.javarosa.org/devicereport'


class DevicelogMigrationPillowTest(TestCase):

    def setUp(self):
        self.pillow = DevicelogMigrationPillow()
        self.pillow.is_migrating = False

        self.assertEqual(self.pillow.couch_db.uri, XFormInstance.get_db().uri)
        self.assertEqual(self.pillow.dest_db.uri, XFormInstanceDevicelog.get_db().uri)

        self.sample_doc = XFormInstance.wrap({
            'xmlns': DEVICELOG_XMLNS,
            'domain': 'ben',
        })
        self.sample_doc.save()

    def tearDown(self):
        try:
            doc = XFormInstanceDevicelog.get(self.sample_doc._id)
        except ResourceNotFound:
            pass
        else:
            doc.delete()

        self.sample_doc.delete()

    def test_filter(self):
        not_matching = [
            dict(xmlns="wrong"),
        ]
        for document in not_matching:
            self.assertFalse(self.pillow.python_filter(document))

        self.assertTrue(self.pillow.python_filter(
            dict(xmlns=DEVICELOG_XMLNS)
        ))

    def test_change_transport(self):
        self.pillow.change_transport(self.sample_doc.to_json())

        self.assertIsNotNone(XFormInstanceDevicelog.get(self.sample_doc._id))

    def test_change_trigger(self):
        self.pillow.change_transport(self.sample_doc.to_json())
        self.pillow.change_trigger(dict(deleted=True, id=self.sample_doc._id, doc=self.sample_doc.to_json()))

        with self.assertRaises(ResourceNotFound):
            XFormInstanceDevicelog.get(self.sample_doc._id)


class DevicelogMigrationPillowIntegrationTest(TestCase):

    def setUp(self):
        self.pillow = DevicelogMigrationPillow()
        self.domain = Domain(
            name="test-domain-sub",
            is_active=True,
        )
        self.domain.save()

    def tearDown(self):
        XFormInstance.get_db().delete_docs(XFormInstance.get_db().all_docs().all())
        XFormInstanceDevicelog.get_db().delete_docs(XFormInstanceDevicelog.get_db().all_docs().all())

    def _add_xforms(self, n=5):
        docs = []
        for i in xrange(n):
            doc = XFormInstance.wrap({'xmlns': DEVICELOG_XMLNS, 'domain': self.domain.name})
            doc.save()
            docs.append(doc)
        return docs

    def test_migration_integration(self):
        """
        This tests the process of first copying docs to target database and then running pillow on new
        changes. It should follow this order:

            1. Run copy_migrate to initially seed database. Pillow will be running but won't process until
            migration is finished
            2. copy_migrate finishes. MigrationPillow updates its seq to the seq at the beginning of the
            migrate and begins to process new changes.
        """

        to_add = 5
        docs = self._add_xforms(to_add)

        for doc in docs:
            self.assertIsNotNone(XFormInstance.get(doc['_id']))
            with self.assertRaises(ResourceNotFound):
                XFormInstanceDevicelog.get(doc['_id'])

        doc = self.pillow.get_checkpoint()

        management.call_command(
            'couch_migrate_devicelogs',
            os.path.join(
                settings.FILEPATH,
                'corehq/apps/cleanup/management/commands/couch_migrations/devicelogs.json',
            ),
            copy=True
        )
        for doc in docs:
            self.assertIsNotNone(XFormInstance.get(doc['_id']))
            self.assertIsNotNone(XFormInstanceDevicelog.get(doc['_id']))

        doc = self.pillow.get_checkpoint()

        # After copy completion should be able to successfully set checkpoint to migration seq
        self.assertFalse(self.pillow.get_checkpoint()['is_migrating'])
