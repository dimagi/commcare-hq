from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.tanzania.reminders import STOP_CONFIRM
from custom.ilsgateway.tests import ILSTestScript
from custom.logistics.tests.utils import bootstrap_user


class TestStop(ILSTestScript):

    def setUp(self):
        super(TestStop, self).setUp()

    def test_stop(self):
        bootstrap_user(self.loc1, username='stop_person', domain=self.domain.name, phone_number='643',
                       first_name='stop', last_name='Person')

        script = """
          643 > stop
          643 < {0}
        """.format(unicode(STOP_CONFIRM))
        self.run_script(script)
        contact = CommCareUser.get_by_username('stop_person')
        self.assertFalse(contact.is_active)
