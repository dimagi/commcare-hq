import uuid

from couchdbkit import ResourceConflict
from couchdbkit.exceptions import ResourceNotFound
from decimal import Decimal
from django.test import TestCase, SimpleTestCase, override_settings
from django.test.client import RequestFactory

from corehq.toggles import (
    NAMESPACE_USER,
    NAMESPACE_DOMAIN,
    TAG_CUSTOM,
    PredictablyRandomToggle,
    StaticToggle,
    deterministic_random,
    DynamicallyPredictablyRandomToggle,
    NAMESPACE_EMAIL_DOMAIN,
)
from toggle.shortcuts import (
    namespaced_item,
    find_users_with_toggle_enabled,
    find_domains_with_toggle_enabled,
)
from .models import generate_toggle_id, Toggle
from .shortcuts import toggle_enabled, set_toggle
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser


class ToggleTestCase(TestCase):
    def setUp(self):
        super(ToggleTestCase, self).setUp()
        self.slug = uuid.uuid4().hex

    def tearDown(self):
        try:
            toggle = Toggle.get(self.slug)
        except ResourceNotFound:
            pass
        else:
            toggle.delete()
        super(ToggleTestCase, self).tearDown()

    def test_generate_id(self):
        self.assertEqual('hqFeatureToggle-sluggy', generate_toggle_id('sluggy'))

    def test_save_and_get_id(self):
        users = ['bruce', 'alfred']
        toggle = Toggle(slug=self.slug, enabled_users=users)
        toggle.save()
        self.assertEqual(generate_toggle_id(self.slug), toggle._id)
        for id in (toggle._id, self.slug):
            fromdb = Toggle.get(id)
            self.assertEqual(self.slug, fromdb.slug)
            self.assertEqual(users, fromdb.enabled_users)

    def test_no_overwrite(self):
        existing = Toggle(slug=self.slug)
        existing.save()
        conflict = Toggle(slug=self.slug)
        try:
            conflict.save()
            self.fail('saving a toggle on top of an existing document should not be allowed')
        except ResourceConflict:
            pass

    def test_toggle_enabled(self):
        users = ['prof', 'logan']
        toggle = Toggle(slug=self.slug, enabled_users=users)
        toggle.save()
        self.assertTrue(toggle_enabled(self.slug, 'prof'))
        self.assertTrue(toggle_enabled(self.slug, 'logan'))
        self.assertFalse(toggle_enabled(self.slug, 'richard'))
        self.assertFalse(toggle_enabled('gotham', 'prof'))

    def test_add_remove(self):
        toggle = Toggle(slug=self.slug, enabled_users=['petyr', 'jon'])
        toggle.save()
        rev = toggle._rev
        self.assertTrue('jon' in toggle.enabled_users)
        self.assertTrue('petyr' in toggle.enabled_users)

        # removing someone who doesn't exist shouldn't do anything
        toggle.remove('robert')
        self.assertEqual(rev, toggle._rev)

        # removing someone should save it and update toggle
        toggle.remove('jon')
        next_rev = toggle._rev
        self.assertNotEqual(rev, next_rev)
        self.assertFalse('jon' in toggle.enabled_users)
        self.assertTrue('petyr' in toggle.enabled_users)

        # adding someone who already exists should do nothing
        toggle.add('petyr')
        self.assertEqual(next_rev, toggle._rev)

        # adding someone should save it and update toggle
        toggle.add('ned')
        self.assertNotEqual(next_rev, toggle._rev)
        self.assertTrue('ned' in toggle.enabled_users)
        self.assertTrue('petyr' in toggle.enabled_users)
        self.assertFalse('jon' in toggle.enabled_users)

    def test_set_toggle(self):
        toggle = Toggle(slug=self.slug, enabled_users=['benjen', 'aemon'])
        toggle.save()

        self.assertTrue(toggle_enabled(self.slug, 'benjen'))
        self.assertTrue(toggle_enabled(self.slug, 'aemon'))

        set_toggle(self.slug, 'benjen', False)
        self.assertFalse(toggle_enabled(self.slug, 'benjen'))
        self.assertTrue(toggle_enabled(self.slug, 'aemon'))

        set_toggle(self.slug, 'jon', True)
        self.assertTrue(toggle_enabled(self.slug, 'jon'))
        self.assertFalse(toggle_enabled(self.slug, 'benjen'))
        self.assertTrue(toggle_enabled(self.slug, 'aemon'))


@override_settings(DISABLE_RANDOM_TOGGLES=False)
class PredictablyRandomToggleSimpleTests(SimpleTestCase):

    def test_deterministic(self):
        self.assertEqual(
            deterministic_random("[None, 'domain']:test_toggle:diana"),
            0.5358778226236243
        )

    def test_all_namespaces_none_given(self):
        toggle = PredictablyRandomToggle(
            'test_toggle',
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_USER, NAMESPACE_DOMAIN],
            randomness=0.99
        )
        self.assertTrue(toggle.enabled('diana'))

    def test_user_namespace_invalid(self):
        toggle = PredictablyRandomToggle(
            'test_toggle',
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_USER],
            randomness=0.99
        )
        with self.assertRaises(ValueError):
            toggle.enabled('jessica')

    def test_domain_namespace_invalid(self):
        toggle = PredictablyRandomToggle(
            'test_toggle',
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_DOMAIN],
            randomness=0.99
        )
        with self.assertRaises(ValueError):
            toggle.enabled('marvel')

    def test_user_namespace_enabled(self):
        toggle = PredictablyRandomToggle(
            'test_toggle',
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_USER],
            randomness=0.99
        )
        self.assertTrue(toggle.enabled('arthur', namespace=NAMESPACE_USER))

    def test_domain_namespace_enabled(self):
        toggle = PredictablyRandomToggle(
            'test_toggle',
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_DOMAIN],
            randomness=0.99
        )
        self.assertTrue(toggle.enabled('dc', namespace=NAMESPACE_DOMAIN))


class PredictablyRandomToggleTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(PredictablyRandomToggleTests, cls).setUpClass()
        cls.user_toggle = Toggle(
            slug='user_toggle',
            enabled_users=['arthur', 'diana'])
        cls.user_toggle.save()
        cls.domain_toggle = Toggle(
            slug='domain_toggle',
            enabled_users=[namespaced_item('dc', NAMESPACE_DOMAIN)])
        cls.domain_toggle.save()

    @classmethod
    def tearDownClass(cls):
        cls.user_toggle.delete()
        cls.domain_toggle.delete()
        super(PredictablyRandomToggleTests, cls).tearDownClass()

    @override_settings(DISABLE_RANDOM_TOGGLES=False)
    def test_user_namespace_disabled(self):
        toggle = PredictablyRandomToggle(
            'user_toggle',
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_USER],
            randomness=0.01
        )
        self.assertTrue(toggle.enabled('diana', namespace=NAMESPACE_USER))
        self.assertFalse(toggle.enabled('jessica', namespace=NAMESPACE_USER))

    @override_settings(DISABLE_RANDOM_TOGGLES=False)
    def test_domain_namespace_disabled(self):
        toggle = PredictablyRandomToggle(
            'domain_toggle',
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_DOMAIN],
            randomness=0.01
        )
        self.assertTrue(toggle.enabled('dc', namespace=NAMESPACE_DOMAIN))
        self.assertFalse(toggle.enabled('marvel', namespace=NAMESPACE_DOMAIN))


class DyanmicPredictablyRandomToggleTests(TestCase):

    def test_default_randomness_no_doc(self):
        for randomness in [0, .5, 1]:
            toggle = DynamicallyPredictablyRandomToggle(
                'dynamic_toggle_no_doc{}'.format(randomness),
                'A toggle for testing',
                TAG_CUSTOM,
                [NAMESPACE_USER],
                default_randomness=randomness,
            )
            self.assertEqual(randomness, toggle.randomness)

    def test_default_randomness_doc_but_no_value(self):
        for randomness in [0, .5, 1]:
            toggle = DynamicallyPredictablyRandomToggle(
                'dynamic_toggle_no_value{}'.format(randomness),
                'A toggle for testing',
                TAG_CUSTOM,
                [NAMESPACE_USER],
                default_randomness=randomness,
            )
            db_toggle = Toggle(slug=toggle.slug)
            db_toggle.save()
            self.addCleanup(db_toggle.delete)
            self.assertEqual(randomness, toggle.randomness)

    def test_override_default_randomness_decimal(self):
        self._run_toggle_overrride_test(Decimal('.5'), .5, 'decimal')

    def test_override_default_randomness_float(self):
        self._run_toggle_overrride_test(.5, .5, 'float')

    def test_override_default_randomness_string(self):
        self._run_toggle_overrride_test('.5', .5, 'string')

    def test_override_default_randomness_invalid(self):
        default_randomness = .1
        self._run_toggle_overrride_test('not-a-number', default_randomness, 'invalid',
                                        default_randomness=default_randomness)

    def _run_toggle_overrride_test(self, input_override, expected_override, test_id, default_randomness=0):
        toggle = DynamicallyPredictablyRandomToggle(
            'override_dynamic_toggle_{}'.format(test_id),
            'A toggle for testing',
            TAG_CUSTOM,
            [NAMESPACE_USER],
            default_randomness=default_randomness,
        )
        db_toggle = Toggle(slug=toggle.slug)
        setattr(db_toggle, DynamicallyPredictablyRandomToggle.RANDOMNESS_KEY, input_override)
        db_toggle.save()
        db_toggle = Toggle.get(toggle.slug)
        self.addCleanup(db_toggle.delete)
        self.assertEqual(expected_override, toggle.randomness)


class ShortcutTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ShortcutTests, cls).setUpClass()
        cls.users = ['arthur', 'diane']
        cls.user_toggle = Toggle(
            slug='user_toggle',
            enabled_users=cls.users)
        cls.user_toggle.save()
        cls.domain = 'dc'
        cls.domain_toggle = Toggle(
            slug='domain_toggle',
            enabled_users=[namespaced_item(cls.domain, NAMESPACE_DOMAIN)])
        cls.domain_toggle.save()

    @classmethod
    def tearDownClass(cls):
        cls.user_toggle.delete()
        cls.domain_toggle.delete()
        super(ShortcutTests, cls).tearDownClass()

    def test_find_users_with_toggle_enabled(self):
        user_toggle = StaticToggle(
            'user_toggle',
            'A test toggle',
            TAG_CUSTOM,
            [NAMESPACE_USER]
        )
        users = find_users_with_toggle_enabled(user_toggle)
        self.assertEqual(set(users), set(self.users))

    def test_find_domains_with_toggle_enabled(self):
        domain_toggle = StaticToggle(
            'domain_toggle',
            'A test toggle',
            TAG_CUSTOM,
            [NAMESPACE_USER]
        )
        domain, = find_domains_with_toggle_enabled(domain_toggle)
        self.assertEqual(domain, self.domain)


class NamespaceTests(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='toggledomain', is_active=True)
        cls.domain.save()

        cls.user = WebUser(username='johndoe@somedomain.com')
        cls.user.save()

        cls.request = RequestFactory()
        cls.request.user = cls.user
        cls.request.domain = cls.domain

        cls.second_domain = Domain(name='toggleotherdomain', is_active=True)
        cls.second_domain.save()

        cls.second_user = WebUser(username='jakerow@otherdomain.com')
        cls.second_user.save()

        cls.second_request = RequestFactory()
        cls.second_request.user = cls.second_user
        cls.second_request.domain = cls.second_domain

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.second_domain.delete()
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.second_user.delete(cls.domain.name, deleted_by=None)

    def test_email_domain_namespace(self):
        email_domain_toggle = StaticToggle(
            'email_domain_namespace_toggle',
            'A test toggle',
            TAG_CUSTOM,
            [NAMESPACE_EMAIL_DOMAIN]
        )
        email_domain_toggle.set('somedomain.com', True, namespace=NAMESPACE_EMAIL_DOMAIN)
        self.assertTrue(email_domain_toggle.enabled(self.user.username))
        self.assertFalse(email_domain_toggle.enabled(self.second_user.username))
        self.assertTrue(email_domain_toggle.enabled_for_request(self.request))
        self.assertFalse(email_domain_toggle.enabled_for_request(self.second_request))

    def test_domain_namespace(self):
        domain_toggle = StaticToggle(
            'domain_namespace_toggle',
            'A test toggle',
            TAG_CUSTOM,
            [NAMESPACE_DOMAIN]
        )
        domain_toggle.set(self.domain.name, True, namespace=NAMESPACE_DOMAIN)
        self.assertTrue(domain_toggle.enabled(self.domain.name))
        self.assertFalse(domain_toggle.enabled(self.second_domain.name))
        self.assertTrue(domain_toggle.enabled_for_request(self.request))
        self.assertFalse(domain_toggle.enabled_for_request(self.second_request))

    def test_user_namespace(self):
        user_toggle = StaticToggle(
            'user_namespace_toggle',
            'A test toggle',
            TAG_CUSTOM,
            [NAMESPACE_USER]
        )
        user_toggle.set(self.user.username, True, namespace=NAMESPACE_USER)
        self.assertTrue(user_toggle.enabled(self.user.username))
        self.assertFalse(user_toggle.enabled(self.second_user.username))
        self.assertTrue(user_toggle.enabled_for_request(self.request))
        self.assertFalse(user_toggle.enabled_for_request(self.second_request))
