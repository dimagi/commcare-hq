from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import PhoneNumber
from couchdbkit import ResourceNotFound
from datetime import datetime, timedelta
from django.test import TestCase
import random
import string
from time import sleep


class BaseMigrationTestCase(TestCase):

    def setUp(self):
        self.domain = 'test-sms-sql-migration'
        self.deleteAllLogs()

    def deleteAllLogs(self):
        for obj in VerifiedNumber.view(
            'phone_numbers/verified_number_by_domain',
            startkey=[self.domain],
            endkey=[self.domain, {}],
            include_docs=True,
            reduce=False
        ).all():
            obj.delete()

        PhoneNumber.objects.filter(domain=self.domain).delete()

    def tearDown(self):
        self.deleteAllLogs()

    def randomBoolean(self):
        return [True, False][random.randint(0, 1)]

    def randomString(self, length=10):
        return ''.join([random.choice(string.lowercase) for i in range(length)])

    def randomInteger(self, beginning=0, end=1000):
        return random.randint(beginning, end)

    def randomDateTime(self, max_lookback=500000):
        result = datetime.utcnow()
        result -= timedelta(minutes=random.randint(0, max_lookback))
        result = result.replace(microsecond=0)
        return result

    def checkFieldValues(self, object1, object2, fields):
        for field_name in fields:
            value1 = getattr(object1, field_name)
            value2 = getattr(object2, field_name)
            self.assertIsNotNone(value1)
            self.assertIsNotNone(value2)
            self.assertEqual(value1, value2)


class PhoneNumberMigrationTestCase(BaseMigrationTestCase):

    def getCouchCount(self):
        result = VerifiedNumber.view(
            'phone_numbers/verified_number_by_domain',
            startkey=[self.domain],
            endkey=[self.domain, {}],
            include_docs=False,
            reduce=True
        ).all()
        return result[0]['value'] if result else 0

    def getSQLCount(self):
        return PhoneNumber.objects.filter(domain=self.domain).count()

    def setRandomCouchObjectValues(self, obj):
        obj.domain = self.domain
        obj.owner_doc_type = self.randomString()
        obj.owner_id = self.randomString()
        obj.phone_number = self.randomString()
        obj.backend_id = self.randomString()
        obj.ivr_backend_id = self.randomString()
        obj.verified = self.randomBoolean()
        obj.contact_last_modified = self.randomDateTime()

    def setRandomSQLObjectValues(self, obj):
        obj.domain = self.domain
        obj.owner_doc_type = self.randomString()
        obj.owner_id = self.randomString()
        obj.phone_number = self.randomString()
        obj.backend_id = self.randomString()
        obj.ivr_backend_id = self.randomString()
        obj.verified = self.randomBoolean()
        obj.contact_last_modified = self.randomDateTime()

    def testCouchSyncToSQL(self):
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

        # Test Create
        couch_obj = VerifiedNumber()
        self.setRandomCouchObjectValues(couch_obj)
        couch_obj.save()

        sleep(1)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)

        sql_obj = PhoneNumber.objects.get(couch_id=couch_obj._id)
        self.checkFieldValues(couch_obj, sql_obj, PhoneNumber._migration_get_fields())
        self.assertTrue(VerifiedNumber.get_db().get_rev(couch_obj._id).startswith('1-'))

        # Test Update
        self.setRandomCouchObjectValues(couch_obj)
        couch_obj.save()

        sleep(1)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)
        sql_obj = PhoneNumber.objects.get(couch_id=couch_obj._id)
        self.checkFieldValues(couch_obj, sql_obj, PhoneNumber._migration_get_fields())
        self.assertTrue(VerifiedNumber.get_db().get_rev(couch_obj._id).startswith('2-'))

        # Test Delete
        couch_id = couch_obj._id
        couch_obj.delete()
        with self.assertRaises(ResourceNotFound):
            VerifiedNumber.get(couch_id)
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

    def testSQLSyncToCouch(self):
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

        # Test Create
        sql_obj = PhoneNumber()
        self.setRandomSQLObjectValues(sql_obj)
        sql_obj.save()

        sleep(1)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)

        couch_obj = VerifiedNumber.get(sql_obj.couch_id)
        self.checkFieldValues(couch_obj, sql_obj, PhoneNumber._migration_get_fields())
        self.assertTrue(VerifiedNumber.get_db().get_rev(couch_obj._id).startswith('2-'))

        # Test Update
        self.setRandomSQLObjectValues(sql_obj)
        sql_obj.save()

        sleep(1)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)
        couch_obj = VerifiedNumber.get(sql_obj.couch_id)
        self.checkFieldValues(couch_obj, sql_obj, PhoneNumber._migration_get_fields())
        self.assertTrue(VerifiedNumber.get_db().get_rev(couch_obj._id).startswith('3-'))

        # Test Delete
        couch_id = couch_obj._id
        sql_obj.delete()
        with self.assertRaises(ResourceNotFound):
            VerifiedNumber.get(couch_id)
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

    def testCouchRetire(self):
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

        # Create
        couch_obj = VerifiedNumber()
        self.setRandomCouchObjectValues(couch_obj)
        couch_obj.save()

        sleep(1)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)

        sql_obj = PhoneNumber.objects.get(couch_id=couch_obj._id)
        self.checkFieldValues(couch_obj, sql_obj, PhoneNumber._migration_get_fields())
        self.assertTrue(VerifiedNumber.get_db().get_rev(couch_obj._id).startswith('1-'))

        # Test retire()
        couch_obj.retire()
        self.assertTrue(VerifiedNumber.get(couch_obj._id).doc_type.endswith('-Deleted'))
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)
