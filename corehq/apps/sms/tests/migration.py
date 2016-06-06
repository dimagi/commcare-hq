from datetime import datetime, timedelta
from django.test import TestCase
import random
import string


class BaseMigrationTestCase(TestCase):

    def setUp(self):
        self.domain = 'test-sms-sql-migration'
        self.deleteAllLogs()

    def deleteAllLogs(self):
        pass

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
