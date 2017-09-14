from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.models import CustomContent
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from django.test import TestCase, override_settings
from mock import patch, call


AVAILABLE_CUSTOM_SCHEDULING_CONTENT = {
    'TEST': 'corehq.messaging.scheduling.tests.test_content.custom_content_handler',
}


def custom_content_handler(recipient, schedule_instance):
    return ['Message 1', 'Message 2']


class TestContent(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestContent, cls).setUpClass()
        cls.user = CommCareUser(phone_numbers=['9990000000000'])

    @override_settings(AVAILABLE_CUSTOM_SCHEDULING_CONTENT=AVAILABLE_CUSTOM_SCHEDULING_CONTENT)
    def test_custom_content(self):
        for cls in (
            AlertScheduleInstance,
            TimedScheduleInstance,
            CaseAlertScheduleInstance,
            CaseTimedScheduleInstance,
        ):
            with patch('corehq.messaging.scheduling.models.content.send_sms_for_schedule_instance') as patched:
                schedule_instance = cls()
                CustomContent(custom_content_id='TEST').send(self.user, schedule_instance)
                patched.assert_has_calls([
                    call(schedule_instance, self.user, '9990000000000', 'Message 1'),
                    call(schedule_instance, self.user, '9990000000000', 'Message 2'),
                ])
