import json
from contextlib import contextmanager
from random import randint
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import AllowedUCRExpressionSettings, Domain
from corehq.apps.domain.utils import (
    encrypt_account_confirmation_info,
    get_domain_url_slug,
    get_serializable_wire_invoice_general_credit,
    guess_domain_language,
    guess_domain_language_for_sms,
    is_domain_in_use,
)
from corehq.apps.users.models import CommCareUser
from corehq.motech.utils import b64_aes_decrypt
from corehq.util.test_utils import generate_cases, unit_testing_only


@unit_testing_only
def delete_all_domains():
    domains = list(Domain.get_all())
    Domain.bulk_delete(domains)


class UtilsTests(TestCase):

    def setUp(self):
        self.domain_name = Domain.generate_name('test_domain')
        domain = Domain(name=self.domain_name)
        domain.save()

    def tearDown(self):
        Domain.get_by_name(self.domain_name).delete()

    def test_guess_domain_language(self):
        for i, lang in enumerate(['en', 'fra', 'fra']):
            app = Application.new_app(domain=self.domain_name, name='app{}'.format(i + 1), lang=lang)
            app.save()
        lang = guess_domain_language(self.domain_name)
        self.assertEqual('fra', lang)

    def test_guess_domain_language_no_apps(self):
        lang = guess_domain_language(self.domain_name)
        self.assertEqual('en', lang)

    def test_guess_domain_language_for_sms_1(self):
        """
        Based on highest count
        """
        for i, lang in enumerate(['en', 'fra', 'fra']):
            app = Application.new_app(domain=self.domain_name, name='app{}'.format(i + 1), lang=lang)
            app.save()
        lang = guess_domain_language_for_sms(self.domain_name)
        self.assertEqual('fra', lang)

    def test_guess_domain_language_for_sms_2(self):
        """
        Based on default when no app present
        """
        lang = guess_domain_language_for_sms(self.domain_name)
        self.assertEqual('en', lang)

    def test_guess_domain_language_for_sms_3(self):
        """
        Based on default when all languages have same count
        """
        for i, lang in enumerate(['fra', 'en', 'ara']):
            app = Application.new_app(domain=self.domain_name, name='app{}'.format(i + 1), lang=lang)
            app.save()
        lang = guess_domain_language_for_sms(self.domain_name)
        self.assertEqual('en', lang)

    def test_guess_domain_language_for_sms_4(self):
        """
        Based on default when two or more languages have same highest count
        """
        for i, lang in enumerate(['fra', 'fra', 'ara', 'ara']):
            app = Application.new_app(domain=self.domain_name, name='app{}'.format(i + 1), lang=lang)
            app.save()
        lang = guess_domain_language_for_sms(self.domain_name)
        self.assertEqual('en', lang)

    def test_guess_domain_language_for_sms_5(self):
        """
        Based on single app present
        """
        for i, lang in enumerate(['ara']):
            app = Application.new_app(domain=self.domain_name, name='app{}'.format(i + 1), lang=lang)
            app.save()
        lang = guess_domain_language_for_sms(self.domain_name)
        self.assertEqual('ara', lang)

    def test_user_info_encryption_decryption(self):
        commcare_user = CommCareUser.create("22", ''.join(str(randint(1, 100))
                                            for i in range(3)), "pass22", None, None)
        encrypted_string = encrypt_account_confirmation_info(commcare_user)
        decrypted = json.loads(b64_aes_decrypt(encrypted_string))
        self.assertIsInstance(decrypted, dict)
        self.assertIsNotNone(decrypted.get("user_id"))
        self.assertIsNotNone(decrypted.get("time"))


class TestGetSerializableWireInvoiceItem(SimpleTestCase):

    def test_empty_list_is_returned_if_general_credit_is_zero(self):
        items = get_serializable_wire_invoice_general_credit(0)
        self.assertFalse(items)

    def test_empty_list_is_returned_if_general_credit_is_less_than_zero(self):
        items = get_serializable_wire_invoice_general_credit(-1)
        self.assertFalse(items)

    def test_item_is_returned_if_general_credit_is_greater_than_zero(self):
        items = get_serializable_wire_invoice_general_credit(1)
        self.assertTrue(items)

    def test_return_value_is_json_serializable(self):
        items = get_serializable_wire_invoice_general_credit(1.5)
        # exception would be raised here if there is an issue
        serialized_items = json.dumps(items)
        self.assertTrue(serialized_items)


@contextmanager
def test_domain(name="domain", skip_full_delete=False):
    """Context manager for use in tests"""
    from corehq.apps.domain.shortcuts import create_domain
    domain = create_domain(name)
    try:
        yield domain
    finally:
        if skip_full_delete:
            Domain.get_db().delete_doc(domain.get_id)
        else:
            domain.delete()


class TestUCRExpressionUtils(TestCase):
    def test_default_value_when_domain_not_exists(self):
        self.assertEqual(
            set(AllowedUCRExpressionSettings.get_allowed_ucr_expressions('blah_domain')),
            {'base_item_expression', 'related_doc'}
        )

    def test_when_domain_exists(self):
        exprn = ['base_item_expression']
        AllowedUCRExpressionSettings.objects.create(domain='test_domain', allowed_ucr_expressions=exprn)
        self.assertEqual(AllowedUCRExpressionSettings.get_allowed_ucr_expressions('test_domain'), exprn)


class TestGetDomainURLSlug(SimpleTestCase):

    def test_defaults_to_project(self):
        self.assertEqual('project', get_domain_url_slug(''))

    def test_one_word(self):
        self.assertEqual('simpletest', get_domain_url_slug('simpletest'))

    def test_name_with_underscore(self):
        self.assertEqual('name-with-underscore', get_domain_url_slug('name_with_underscore'))

    def test_unicode_treated_literally(self):
        self.assertEqual('test-u2500', get_domain_url_slug('test\\u2500'))

    def test_max_length_is_enforced(self):
        # cuts off entire word if exceeds max_length
        self.assertEqual('test', get_domain_url_slug('test-length', max_length=8))

    @generate_cases([
        ('long name with stop words in it', 30, 'name-stop-words'),
        ('long name with stop words in it', 14, 'name-stop'),
    ])
    def test_stop_words_excluded(self, hr_name, max_length, expected):
        self.assertEqual(expected, get_domain_url_slug(hr_name, max_length=max_length))


class IsDomainInUseTests(SimpleTestCase):

    def test_domain_in_use_returns_true(self):
        self.mock_get_by_name.return_value = self.domain_actively_in_use
        self.assertTrue(is_domain_in_use(self.domain_actively_in_use.name))

    def test_paused_domain_returns_true(self):
        self.mock_get_by_name.return_value = self.paused_domain
        self.assertTrue(is_domain_in_use(self.paused_domain.name))

    def test_deleted_domain_returns_false(self):
        self.mock_get_by_name.return_value = self.deleted_domain
        self.assertFalse(is_domain_in_use(self.deleted_domain.name))

    def test_active_deleted_domain_returns_false(self):
        # should not be possible to get into this state (active + deleted)
        self.mock_get_by_name.return_value = self.active_deleted_domain
        self.assertFalse(is_domain_in_use(self.active_deleted_domain.name))

    def test_non_existent_domain_returns_false(self):
        self.mock_get_by_name.return_value = None
        self.assertFalse(is_domain_in_use('non-existent-domain'))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_actively_in_use = Domain(doc_type="Domain", name="domain-in-use", is_active=True)
        cls.paused_domain = Domain(doc_type="Domain", name="domain-paused", is_active=False)
        cls.deleted_domain = Domain(doc_type="Domain-Deleted", name="domain-deleted", is_active=False)
        # should not be possible to get into this state
        cls.active_deleted_domain = Domain(doc_type="Domain-Deleted", name="domain-deleted", is_active=True)

    def setUp(self):
        self.get_by_name_patcher = patch('corehq.apps.domain.utils.Domain.get_by_name')
        self.mock_get_by_name = self.get_by_name_patcher.start()
        self.addCleanup(self.get_by_name_patcher.stop)


delete_es_docs_patch = patch('corehq.apps.domain.deletion._delete_es_docs')


def patch_domain_deletion():
    """Do not delete docs in Elasticsearch when deleting a domain

    Without this, every test that deletes a domain would need to be
    decorated with `@es_test`.
    """
    # Use __enter__ and __exit__ to start/stop so patch.stopall() does not stop it.
    assert settings.UNIT_TESTING
    delete_es_docs_patch.__enter__()


@contextmanager
def suspend(patch_obj):
    """Contextmanager/decorator to suspend an active patch

    Usage as decorator:

        @suspend(delete_es_docs_patch)
        def test_something():
            ...  # do thing with ES docs deletion

    Usage as context manager:

        with suspend(delete_es_docs_patch):
            ...  # do thing with ES docs deletion
    """
    assert settings.UNIT_TESTING
    patch_obj.__exit__(None, None, None)
    try:
        yield
    finally:
        patch_obj.__enter__()
