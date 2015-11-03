from corehq.apps.users.models import CommCareUser
from custom.ewsghana.handlers import STOP_MESSAGE
from custom.ewsghana.tests.handlers.utils import EWSScriptTest


class TestStop(EWSScriptTest):

    def test_stop(self):
        a = """
           5551234 > stop
           5551234 < {}
           """.format(unicode(STOP_MESSAGE))
        self.run_script(a)
        user = CommCareUser.get(self.user1.get_id)
        self.assertEqual(user.user_data['needs_reminders'], "False")
