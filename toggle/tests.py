from couchdbkit import ResourceConflict
from couchdbkit.ext.django.schema import Document
from django.test import TestCase
from .models import generate_toggle_id, Toggle
from .shortcuts import toggle_enabled


class ToggleTestCase(TestCase):
    
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
