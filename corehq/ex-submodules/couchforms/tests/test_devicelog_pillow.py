import os

from django.test import TestCase
from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.pillows.migration import DevicelogMigrationPillow


class DevicelogMigrationPillowTest(TestCase, TestFileMixin):
    file_path = ('data', 'xforms')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.pillow = DevicelogMigrationPillow()

    def tearDown(self):
        pass

    def test_basic_devicelog_pillow(self):
        devicelog_json = self.get_json('devicelog-basic')
        source = self.pillow.source_db()
        source.save_doc(devicelog_json)

        self.pillow.change_transport(devicelog_json)

        dest = self.pillow.dest_db()
        doc = dest.get(devicelog_json['_id'])

        self.assertIsNotNone(doc)

    def test_deleted_devicelog(self):
        devicelog_json = self.get_json('devicelog-basic')
        source = self.pillow.source_db()
        source.save_doc(devicelog_json)

        self.pillow.change_transport(devicelog_json)

        dest = self.pillow.dest_db()
        doc = dest.get(devicelog_json['_id'])

        self.assertIsNotNone(doc)

        source.delete_doc(devicelog_json['_id'])
        self.pillow.change_trigger({'deleted': True, 'id': devicelog_json['_id']})

        with self.assertRaises(ResourceNotFound):
            dest.get(devicelog_json['_id'])
