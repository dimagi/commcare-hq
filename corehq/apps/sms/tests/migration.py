from datetime import datetime, timedelta
from django.test import TestCase
from couchdbkit import ResourceNotFound
import random
import string


class BaseMigrationTestCase(TestCase):

    def setUp(self):
        self.domain = 'test-sms-sql-migration'

    def deleteAllObjects(self):
        pass

    def tearDown(self):
        self.deleteAllObjects()

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

    def randomList(self, min_items=0, max_items=2):
        return [self.randomString() for i in range(random.randint(min_items, max_items))]

    def randomChoice(self, choices):
        return choices[random.randint(0, len(choices) - 1)]

    def randomDict(self, min_items=0, max_items=2):
        return {
            self.randomString(): self.randomString()
            for i in range(random.randint(min_items, max_items))
        }

    def checkFieldValues(self, object1, object2, fields):
        for field_name in fields:
            value1 = getattr(object1, field_name)
            value2 = getattr(object2, field_name)
            self.assertIsNotNone(value1)
            self.assertIsNotNone(value2)
            self.assertEqual(value1, value2)
