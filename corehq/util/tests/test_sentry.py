import uuid
from django.test import SimpleTestCase, override_settings
from corehq.util.sentry import looks_sensitive


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
        with override_settings(COUCH_DATABASES=overridden_dbs):
            self.assertTrue(looks_sensitive('something leaking the {}'.format(couch_pw)))
            self.assertTrue(looks_sensitive('something else leaking the {}'.format(couch_pw2)))
            self.assertFalse(looks_sensitive('something not leaking the password'.format(couch_pw)))
