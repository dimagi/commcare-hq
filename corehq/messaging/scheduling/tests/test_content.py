from __future__ import absolute_import
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.models import Schedule, Content, CustomContent
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
        cls.domain = 'test-content'
        cls.user = CommCareUser(phone_numbers=['9990000000000'], language='es')

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

    def test_get_translation_from_message_dict(self):
        message_dict = {}
        schedule = Schedule(domain=self.domain)

        # Empty message dict results in no message
        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            ''
        )

        # Non-translated message is the most general default
        message_dict['*'] = 'non-translated message'
        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['*']
        )

        # Domain default language override
        translation_doc = StandaloneTranslationDoc(domain=self.domain, area='sms', langs=['en', 'es'])
        translation_doc.save()
        self.addCleanup(translation_doc.delete)

        message_dict['en'] = 'english message'
        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['en']
        )

        # Schedule default language override
        schedule.default_language_code = 'hin'

        message_dict['hin'] = 'hindi message'
        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['hin']
        )

        # User-preferred language override
        message_dict['es'] = 'spanish message'
        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['es']
        )
