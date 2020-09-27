from datetime import datetime, timedelta

from django.core.management import call_command
from django.test import TestCase

from corehq.apps.mobile_auth.management.commands.populate_mobileauthkeyrecord import Command
from corehq.apps.mobile_auth.models import (
    MobileAuthKeyRecord,
    SQLMobileAuthKeyRecord,
)
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from dimagi.utils.parsing import string_to_utc_datetime


class TestCouchToSQLMobileAuth(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = MobileAuthKeyRecord.get_db()

    def tearDown(self):
        SQLMobileAuthKeyRecord.objects.all().delete()
        for doc in get_all_docs_with_doc_types(self.db, ['MobileAuthKeyRecord']):
            MobileAuthKeyRecord.wrap(doc).delete()
        super().tearDown()

    def test_diff_identical(self):
        key = '234'
        valid = datetime.utcnow()
        expires = valid + timedelta(days=30)
        couch = MobileAuthKeyRecord(domain='my-domain', user_id='123', valid=valid, expires=expires, key=key)
        sql = SQLMobileAuthKeyRecord(domain='my-domain', user_id='123', valid=valid, expires=expires, key=key)
        self.assertIsNone(Command.diff_couch_and_sql(couch.to_json(), sql))

    def test_diff_top_level_attributes(self):
        valid = datetime.utcnow()
        expires1 = valid + timedelta(days=30)
        expires2 = valid + timedelta(days=31)
        couch = MobileAuthKeyRecord(domain='my-domain', user_id='123', valid=valid, expires=expires1)
        sql = SQLMobileAuthKeyRecord(domain='other-domain', user_id='123', valid=valid, expires=expires2)

        (domain_diff, key_diff, expires_diff) = Command.diff_couch_and_sql(couch.to_json(), sql).split("\n")
        self.assertEqual(domain_diff, "domain: couch value 'my-domain' != sql value 'other-domain'")
        self.assertRegex(
            key_diff,
            r"key: couch value '.+' != sql value '.+'"
        )
        self.assertRegex(
            expires_diff,
            r"expires: couch value '\d{4}-..-.. ..:..:..\.\d+' != sql value '\d{4}-..-.. ..:..:..\.\d+'"
        )

    def test_sync_to_couch(self):
        valid = datetime.utcnow()
        expires = valid + timedelta(days=30)
        sql = SQLMobileAuthKeyRecord(domain='my-domain', user_id='123', valid=valid, expires=expires)
        sql.save()

        actual = self.db.get(sql.id)
        self.assertEqual(actual['domain'], 'my-domain')
        self.assertEqual(actual['user_id'], '123')
        self.assertEqual(string_to_utc_datetime(actual['valid']), valid)
        self.assertEqual(string_to_utc_datetime(actual['expires']), expires)
        self.assertEqual(actual['type'], 'AES256')
        self.assertEqual(actual['key'], sql.key)

    def test_sync_to_sql(self):
        valid = datetime.utcnow()
        expires = valid + timedelta(days=30)
        couch = MobileAuthKeyRecord(domain='my-domain', user_id='123', valid=valid, expires=expires)
        couch.save()

        actual = SQLMobileAuthKeyRecord.objects.get(id=couch._id)
        self.assertEqual(actual.domain, 'my-domain')
        self.assertEqual(actual.user_id, '123')
        self.assertEqual(actual.valid, valid)
        self.assertEqual(actual.expires, expires)
        self.assertEqual(actual.type, 'AES256')
        self.assertEqual(actual.key, couch.key)

    def test_migration(self):
        valid = datetime.utcnow()
        expires = valid + timedelta(days=30)
        couch = MobileAuthKeyRecord(domain='my-domain', user_id='123', valid=valid, expires=expires)
        couch.save()

        # Create any sql objects that didn't exist pre-migration
        call_command('populate_mobileauthkeyrecord')
        actual = SQLMobileAuthKeyRecord.objects.get(id=couch._id)
        self.assertEqual(actual.domain, 'my-domain')
        self.assertEqual(actual.user_id, '123')
        self.assertEqual(actual.valid, valid)
        self.assertEqual(actual.expires, expires)
        self.assertEqual(actual.type, 'AES256')
        self.assertEqual(actual.key, couch.key)

        # Update any pre-existing sql objects
        couch['domain'] = 'other-domain'
        couch['user_id'] = '456'
        couch.save(sync_to_sql=False)
        call_command('populate_mobileauthkeyrecord')
        actual = SQLMobileAuthKeyRecord.objects.get(id=couch._id)
        self.assertEqual(actual.domain, 'other-domain')
        self.assertEqual(actual.user_id, '456')
        self.assertEqual(actual.valid, valid)
        self.assertEqual(actual.expires, expires)
        self.assertEqual(actual.type, 'AES256')
        self.assertEqual(actual.key, couch.key)
