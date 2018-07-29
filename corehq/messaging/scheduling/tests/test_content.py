from __future__ import absolute_import
from __future__ import unicode_literals
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
from mock import Mock


AVAILABLE_CUSTOM_SCHEDULING_CONTENT = {
    'TEST': ['corehq.messaging.scheduling.tests.test_content.custom_content_handler', "Test"]
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
            content = CustomContent(custom_content_id='TEST')
            content.set_context(schedule_instance=cls())
            self.assertEqual(content.get_list_of_messages(self.user), ['Message 1', 'Message 2'])

    def test_get_translation_empty_message(self):
        message_dict = {}
        content = Content()
        content.set_context(schedule_instance=Mock(memoized_schedule=Schedule(domain=self.domain)))

        self.assertEqual(
            content.get_translation_from_message_dict(
                self.domain,
                message_dict,
                self.user.get_language_code()
            ),
            ''
        )

    def test_get_translation_general_default(self):
        message_dict = {
            '*': 'non-translated message',
        }
        content = Content()
        content.set_context(schedule_instance=Mock(memoized_schedule=Schedule(domain=self.domain)))

        self.assertEqual(
            content.get_translation_from_message_dict(
                self.domain,
                message_dict,
                self.user.get_language_code()
            ),
            message_dict['*']
        )

    def test_get_translation_domain_default(self):
        message_dict = {
            '*': 'non-translated message',
            'en': 'english message',
        }
        content = Content()
        content.set_context(schedule_instance=Mock(memoized_schedule=Schedule(domain=self.domain)))

        self.assertEqual(
            content.get_translation_from_message_dict(
                self.domain,
                message_dict,
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
        content = Content()
        content.set_context(
            schedule_instance=Mock(memoized_schedule=Schedule(domain=self.domain, default_language_code='hin'))
        )

        self.assertEqual(
            content.get_translation_from_message_dict(
                self.domain,
                message_dict,
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
        content = Content()
        content.set_context(
            schedule_instance=Mock(memoized_schedule=Schedule(domain=self.domain, default_language_code='hin'))
        )

        self.assertEqual(
            content.get_translation_from_message_dict(
                self.domain,
                message_dict,
                self.user.get_language_code()
            ),
            message_dict['es']
        )
