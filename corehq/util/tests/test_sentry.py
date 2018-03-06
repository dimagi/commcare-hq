# coding=utf-8
from __future__ import absolute_import
import uuid
from django.test import SimpleTestCase, override_settings
from corehq.util.sentry import HQSanitzeSystemPasswordsProcessor


class HQSentryTest(SimpleTestCase):

    def test_couch_password(self):
        couch_pw = uuid.uuid4().hex
        couch_pw2 = uuid.uuid4().hex
        overridden_dbs = {
            'db{}'.format(i): {
                'COUCH_HTTPS': False,
                'COUCH_SERVER_ROOT': '127.0.0.1:5984',
                'COUCH_USERNAME': 'commcarehq',
                'COUCH_PASSWORD': pw,
                'COUCH_DATABASE_NAME': 'commcarehq',
            }
            for i, pw in enumerate([couch_pw, couch_pw2])
        }
        subs = {
            'pw': couch_pw,
            'pw2': couch_pw2,
        }
        masks = {
            'pw': '********',
            'pw2': '********',
        }
        with override_settings(COUCH_DATABASES=overridden_dbs):
            processor = HQSanitzeSystemPasswordsProcessor(client=None)
            for test in [
                '{pw}',
                'http://username:{pw}@example.com',
                'p1: {pw}, p2: {pw2}',
                'no secrets here',
                u'in दिल्ली  we say {pw}'
            ]:
                formatted_test = test.format(**subs)
                expected_result = test.format(**masks)
                self.assertEqual(expected_result, processor.sanitize('key', formatted_test))

            for edge_case in [
                (None, None),
                ({'foo': 'bar'}, {'foo': 'bar'}),
            ]:
                self.assertEqual(edge_case[1], processor.sanitize('key', edge_case[0]))
