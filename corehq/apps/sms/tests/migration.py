from datetime import datetime, timedelta
from django.test import TestCase
from corehq.apps.reminders.models import (SurveyKeyword, SurveyKeywordAction,
    KEYWORD_ACTION_CHOICES, KEYWORD_RECIPIENT_CHOICES)
from corehq.apps.sms.models import Keyword, KeywordAction
from couchdbkit import ResourceNotFound
import random
import string


class BaseMigrationTestCase(TestCase):

    def setUp(self):
        self.domain = 'test-sms-sql-migration'
        self.deleteAllObjects()

    def deleteAllObjects(self):
        for obj in SurveyKeyword.get_all(self.domain):
            obj.delete()

        Keyword.objects.filter(domain=self.domain).delete()

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


class KeywordMigrationTestCase(BaseMigrationTestCase):

    def getCouchCount(self):
        result = SurveyKeyword.view(
            'reminders/survey_keywords',
            startkey=[self.domain],
            endkey=[self.domain, {}],
            include_docs=False,
            reduce=True,
        ).all()
        if result:
            return result[0]['value']
        return 0

    def getSQLCount(self):
        return Keyword.objects.filter(domain=self.domain).count()

    def setRandomCouchObjectValues(self, obj):
        obj.domain = self.domain
        obj.keyword = self.randomString()
        obj.description = self.randomString()
        obj.delimiter = self.randomString()
        obj.override_open_sessions = self.randomBoolean()
        obj.initiator_doc_type_filter = self.randomList()

        obj.actions = []
        for i in range(random.randint(1, 3)):
            obj.actions.append(SurveyKeywordAction(
                recipient=self.randomChoice(KEYWORD_RECIPIENT_CHOICES),
                recipient_id="{}{}".format(i, self.randomString()),
                action=self.randomChoice(KEYWORD_ACTION_CHOICES),
                message_content=self.randomString(),
                form_unique_id=self.randomString(),
                use_named_args=self.randomBoolean(),
                named_args=self.randomDict(),
                named_args_separator=self.randomString(),
            ))
        obj.save()

    def setRandomSQLObjectValues(self, obj):
        obj.domain = self.domain
        obj.keyword = self.randomString()
        obj.description = self.randomString()
        obj.delimiter = self.randomString()
        obj.override_open_sessions = self.randomBoolean()
        obj.initiator_doc_type_filter = self.randomList()
        obj.save(sync_to_couch=False)

        obj.keywordaction_set.all().delete()
        for i in range(random.randint(1, 3)):
            obj.keywordaction_set.create(
                action=self.randomChoice(KEYWORD_ACTION_CHOICES),
                recipient=self.randomChoice(KEYWORD_RECIPIENT_CHOICES),
                recipient_id="{}{}".format(i, self.randomString()),
                message_content=self.randomString(),
                form_unique_id=self.randomString(),
                use_named_args=self.randomBoolean(),
                named_args=self.randomDict(),
                named_args_separator=self.randomString(),
            )

        # Sync to couch
        obj.save()

    def compareObjects(self, couch_obj, sql_obj):
        keyword_fields = [
            'domain',
            'keyword',
            'description',
            'delimiter',
            'override_open_sessions',
            'initiator_doc_type_filter',
        ]

        keyword_action_fields = [
            'recipient',
            'recipient_id',
            'action',
            'message_content',
            'form_unique_id',
            'use_named_args',
            'named_args',
            'named_args_separator',
        ]

        self.checkFieldValues(couch_obj, sql_obj, keyword_fields)

        self.assertEqual(len(couch_obj.actions), sql_obj.keywordaction_set.all().count())
        couch_actions = sorted(couch_obj.actions, key=lambda obj: obj.recipient_id)
        sql_actions = sql_obj.keywordaction_set.all().order_by('recipient_id')

        for i in range(len(couch_actions)):
            self.checkFieldValues(couch_actions[i], sql_actions[i], keyword_action_fields)

    def testCouchSyncToSQL(self):
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

        # Test Create
        couch_obj = SurveyKeyword()
        self.setRandomCouchObjectValues(couch_obj)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)

        sql_obj = Keyword.objects.get(couch_id=couch_obj._id)
        self.compareObjects(couch_obj, sql_obj)
        self.assertTrue(SurveyKeyword.get_db().get_rev(couch_obj._id).startswith('1-'))

        # Test Update
        self.setRandomCouchObjectValues(couch_obj)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)
        sql_obj = Keyword.objects.get(couch_id=couch_obj._id)
        self.compareObjects(couch_obj, sql_obj)
        self.assertTrue(SurveyKeyword.get_db().get_rev(couch_obj._id).startswith('2-'))

        # Test Delete
        couch_id = couch_obj._id
        couch_obj.delete()
        with self.assertRaises(ResourceNotFound):
            SurveyKeyword.get(couch_id)
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

    def testSQLSyncToCouch(self):
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)

        # Test Create
        sql_obj = Keyword()
        self.setRandomSQLObjectValues(sql_obj)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)

        couch_obj = SurveyKeyword.get(sql_obj.couch_id)
        self.compareObjects(couch_obj, sql_obj)
        self.assertTrue(SurveyKeyword.get_db().get_rev(couch_obj._id).startswith('2-'))

        # Test Update
        self.setRandomSQLObjectValues(sql_obj)
        self.assertEqual(self.getCouchCount(), 1)
        self.assertEqual(self.getSQLCount(), 1)
        couch_obj = SurveyKeyword.get(sql_obj.couch_id)
        self.compareObjects(couch_obj, sql_obj)
        self.assertTrue(SurveyKeyword.get_db().get_rev(couch_obj._id).startswith('3-'))

        # Test Delete
        couch_id = couch_obj._id
        sql_obj.delete()
        with self.assertRaises(ResourceNotFound):
            SurveyKeyword.get(couch_id)
        self.assertEqual(self.getCouchCount(), 0)
        self.assertEqual(self.getSQLCount(), 0)
