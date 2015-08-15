from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.tanzania.reminders import LANGUAGE_CONFIRM
from custom.ilsgateway.tests import ILSTestScript


class ILSLanguageTest(ILSTestScript):

    def setUp(self):
        super(ILSLanguageTest, self).setUp()

    def test_arrived_help(self):
        self.user_fac1.language = 'en'
        self.user_fac1.save()
        language_message = """
            5551234 > language hin
            5551234 < {0}
        """.format(unicode(LANGUAGE_CONFIRM) % dict(language='Hindi'))
        self.run_script(language_message)
        user = CommCareUser.get_by_username('stella')
        self.assertEqual(user.language, 'hin')
