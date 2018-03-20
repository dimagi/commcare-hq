from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import SimpleTestCase

from corehq.motech.repeaters.utils import migrate_repeater


class TestAuthFieldMigration(SimpleTestCase):

    def test_no_auth_field(self):
        doc = {
            "_id": uuid.uuid4().hex,
            "domain": "foo",
        }
        change = migrate_repeater(doc)
        self.assertIsNone(change)

    def test_use_basic_auth(self):
        doc = {
            "_id": uuid.uuid4().hex,
            "domain": "foo",
            "use_basic_auth": True,
        }
        change = migrate_repeater(doc)
        self.assertIsNotNone(change)
        self.assertEqual(change.doc.get("auth_type"), "basic")

    def test_use_no_auth(self):
        doc = {
            "_id": uuid.uuid4().hex,
            "domain": "foo",
            "use_basic_auth": False,
        }
        change = migrate_repeater(doc)
        self.assertIsNotNone(change)
        self.assertTrue("auth_type" not in change.doc)
