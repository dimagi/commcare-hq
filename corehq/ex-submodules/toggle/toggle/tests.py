from couchdbkit import ResourceConflict
from dimagi.ext.couchdbkit import Document
from django.conf import settings
from django.test import TestCase
from .models import generate_toggle_id, Toggle
from .shortcuts import toggle_enabled, set_toggle


class ToggleTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.realcaches = settings.CACHES
        settings.CACHES = {
            'default': {
                'BACKEND':  'django.core.cache.backends.dummy.DummyCache',
            }
        }

    @classmethod
    def tearDownClass(cls):
        settings.CACHES = cls.realcaches

    def test_generate_id(self):
        self.assertEqual('hqFeatureToggle-sluggy', generate_toggle_id('sluggy'))

    def test_save_and_get_id(self):
        slug = 'batcave'
        users = ['bruce', 'alfred']
        toggle = Toggle(slug=slug, enabled_users=users)
        toggle.save()
        self.assertEqual(generate_toggle_id(slug), toggle._id)
        for id in (toggle._id, slug):
            fromdb = Toggle.get(id)
            self.assertEqual(slug, fromdb.slug)
            self.assertEqual(users, fromdb.enabled_users)

    def test_no_overwrite(self):
        slug = 'conflict'
        somedoc = Document(_id=generate_toggle_id(slug))
        Toggle.get_db().save_doc(somedoc)
        conflict = Toggle(slug=slug)
        try:
            conflict.save()
            self.fail('saving a toggle on top of an existing document should not be allowed')
        except ResourceConflict:
            pass

    def test_toggle_enabled(self):
        slug = 'mansion'
        users = ['prof', 'logan']
        toggle = Toggle(slug=slug, enabled_users=users)
        toggle.save()
        self.assertTrue(toggle_enabled(slug, 'prof'))
        self.assertTrue(toggle_enabled(slug, 'logan'))
        self.assertFalse(toggle_enabled(slug, 'richard'))
        self.assertFalse(toggle_enabled('gotham', 'prof'))

    def test_add_remove(self):
        toggle = Toggle(slug='council', enabled_users=['petyr', 'jon'])
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
        slug = 'wall'
        toggle = Toggle(slug=slug, enabled_users=['benjen', 'aemon'])
        toggle.save()
        self.assertTrue(toggle_enabled(slug, 'benjen'))
        self.assertTrue(toggle_enabled(slug, 'aemon'))

        set_toggle(slug, 'benjen', False)
        self.assertFalse(toggle_enabled(slug, 'benjen'))
        self.assertTrue(toggle_enabled(slug, 'aemon'))

        set_toggle(slug, 'jon', True)
        self.assertTrue(toggle_enabled(slug, 'jon'))
        self.assertFalse(toggle_enabled(slug, 'benjen'))
        self.assertTrue(toggle_enabled(slug, 'aemon'))
