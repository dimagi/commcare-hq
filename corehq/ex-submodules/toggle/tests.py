import uuid

from couchdbkit import ResourceConflict
from couchdbkit.exceptions import ResourceNotFound
from django.test import TestCase

from toggle.shortcuts import update_toggle_cache, namespaced_item, clear_toggle_cache
from .models import generate_toggle_id, Toggle
from .shortcuts import toggle_enabled, set_toggle


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

    def test_toggle_cache(self):
        ns = 'ns'
        toggle = Toggle(slug=self.slug, enabled_users=['mojer', namespaced_item('fizbod', ns)])
        toggle.save()

        self.assertTrue(toggle_enabled(self.slug, 'mojer'))
        self.assertFalse(toggle_enabled(self.slug, 'fizbod'))
        self.assertTrue(toggle_enabled(self.slug, 'fizbod', namespace=ns))

        update_toggle_cache(self.slug, 'mojer', False)
        update_toggle_cache(self.slug, 'fizbod', False, namespace=ns)

        self.assertFalse(toggle_enabled(self.slug, 'mojer'))
        self.assertFalse(toggle_enabled(self.slug, 'fizbod', namespace=ns))

        clear_toggle_cache(self.slug, 'mojer')
        clear_toggle_cache(self.slug, 'fizbod', namespace=ns)

        self.assertTrue(toggle_enabled(self.slug, 'mojer'))
        self.assertTrue(toggle_enabled(self.slug, 'fizbod', namespace=ns))
