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
        cls.translation_doc = StandaloneTranslationDoc(domain=cls.domain, area='sms', langs=['en', 'es'])
        cls.translation_doc.save()

    @classmethod
    def tearDownClass(cls):
        cls.translation_doc.delete()
        super(TestContent, cls).tearDownClass()

    @override_settings(AVAILABLE_CUSTOM_SCHEDULING_CONTENT=AVAILABLE_CUSTOM_SCHEDULING_CONTENT)
    def test_custom_content(self):
        for cls in (
            AlertScheduleInstance,
            TimedScheduleInstance,
            CaseAlertScheduleInstance,
            CaseTimedScheduleInstance,
        ):
            schedule_instance = cls()
            result = CustomContent(custom_content_id='TEST').get_list_of_messages(self.user, schedule_instance)
            self.assertEqual(result, ['Message 1', 'Message 2'])

    def test_get_translation_empty_message(self):
        message_dict = {}
        schedule = Schedule(domain=self.domain)

        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            ''
        )

    def test_get_translation_general_default(self):
        message_dict = {
            '*': 'non-translated message',
        }
        schedule = Schedule(domain=self.domain)

        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['*']
        )

    def test_get_translation_domain_default(self):
        message_dict = {
            '*': 'non-translated message',
            'en': 'english message',
        }
        schedule = Schedule(domain=self.domain)

        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['en']
        )

    def test_get_translation_schedule_default(self):
        message_dict = {
            '*': 'non-translated message',
            'en': 'english message',
            'hin': 'hindi message',
        }
        schedule = Schedule(domain=self.domain, default_language_code='hin')

        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['hin']
        )

    def test_get_translation_user_preferred(self):
        message_dict = {
            '*': 'non-translated message',
            'en': 'english message',
            'hin': 'hindi message',
            'es': 'spanish message',
        }
        schedule = Schedule(domain=self.domain, default_language_code='hin')

        self.assertEqual(
            Content.get_translation_from_message_dict(
                message_dict,
                schedule,
                self.user.get_language_code()
            ),
            message_dict['es']
        )
