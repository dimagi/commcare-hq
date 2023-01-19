from unittest.mock import Mock

from django.test import TestCase, override_settings

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sms.forms import (
    LANGUAGE_FALLBACK_NONE,
    LANGUAGE_FALLBACK_SCHEDULE,
    LANGUAGE_FALLBACK_DOMAIN,
    LANGUAGE_FALLBACK_UNTRANSLATED,
)
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.exceptions import EmailValidationException
from corehq.messaging.scheduling.models import (
    Content as AbstractContent,
    CustomContent,
    Schedule as AbstractSchedule,
    EmailContent,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.util.test_utils import unregistered_django_model


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
        cls.domain_obj = create_domain(cls.domain)
        cls.user = CommCareUser(phone_numbers=['9990000000000'], language='es')
        from corehq.apps.sms.util import get_or_create_sms_translations
        cls.sms_translations = get_or_create_sms_translations(cls.domain)
        cls.sms_translations.set_translations('es', {})
        cls.sms_translations.save()

    @classmethod
    def tearDownClass(cls):
        cls.sms_translations.delete()
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
                self.domain_obj,
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
                self.domain_obj,
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
                self.domain_obj,
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
                self.domain_obj,
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
                self.domain_obj,
                message_dict,
                self.user.get_language_code()
            ),
            message_dict['es']
        )

    def test_sms_language_fallback(self):
        message_dict = {
            '*': 'non-translated message',
            'en': 'english message',            # project default
            'hin': 'hindi message',             # schedule default
            'es': 'spanish message',            # user's preferred language
            'kan': 'kannada message',           # arbitrary language to test untranslated case
        }
        user_lang = self.user.get_language_code()
        content = Content()
        content.set_context(
            schedule_instance=Mock(memoized_schedule=Schedule(domain=self.domain, default_language_code='hin'))
        )

        self.domain_obj.sms_language_fallback = LANGUAGE_FALLBACK_NONE
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            message_dict['es']
        )
        message_dict.pop('es')
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            ''
        )

        self.domain_obj.sms_language_fallback = LANGUAGE_FALLBACK_SCHEDULE
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            message_dict['hin']
        )
        message_dict.pop('hin')
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            ''
        )

        self.domain_obj.sms_language_fallback = LANGUAGE_FALLBACK_DOMAIN
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            message_dict['en']
        )
        message_dict.pop('en')
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            ''
        )

        self.domain_obj.sms_language_fallback = LANGUAGE_FALLBACK_UNTRANSLATED
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            message_dict['*']
        )
        message_dict.pop('kan')

        # Default: same as LANGUAGE_FALLBACK_UNTRANSLATED
        self.domain_obj.sms_language_fallback = None
        self.assertEqual(
            content.get_translation_from_message_dict(self.domain_obj, message_dict, user_lang),
            message_dict['*']
        )

    def test_email_validation_valid(self):
        recipient = MockRecipient("test@example.com")
        EmailContent().get_recipient_email(recipient)

    def test_email_validation_empty_email(self):
        recipient = MockRecipient("")
        with self.assertRaises(EmailValidationException) as e:
            EmailContent().get_recipient_email(recipient)
        self.assertEqual(e.exception.error_type, MessagingEvent.ERROR_NO_EMAIL_ADDRESS)

    def test_email_validation_no_email(self):
        recipient = MockRecipient(None)
        with self.assertRaises(EmailValidationException) as e:
            EmailContent().get_recipient_email(recipient)
        self.assertEqual(e.exception.error_type, MessagingEvent.ERROR_NO_EMAIL_ADDRESS)

    def test_email_validation_invalid_email(self):
        recipient = MockRecipient("bob")
        with self.assertRaises(EmailValidationException) as e:
            EmailContent().get_recipient_email(recipient)
        self.assertEqual(e.exception.error_type, MessagingEvent.ERROR_INVALID_EMAIL_ADDRESS)


@unregistered_django_model
class Content(AbstractContent):
    pass


@unregistered_django_model
class Schedule(AbstractSchedule):
    pass


class MockRecipient:
    def __init__(self, email_address):
        self.email_address = email_address

    def get_email(self):
        return self.email_address
