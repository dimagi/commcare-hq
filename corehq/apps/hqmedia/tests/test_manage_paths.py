from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

import json
import os
import re

from mock import patch

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.hqmedia.view_helpers import (
    download_multimedia_paths_rows,
    validate_multimedia_paths_rows,
    update_multimedia_paths,
)
from io import open


@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
class ManagePathsTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def _get_menu_media(self, lang):
        return {
            'en': 'jr://file/commcare/module0_en.png',
            'fra': 'jr://file/commcare/module0_fra.png',
        }[lang]

    def _get_form_media(self, lang):
        return {
            'en': 'jr://file/commcare/image/data/question1-fn3fu1.jpg',
            'fra': 'jr://file/commcare/image/data/question1-1ppout.jpg',
        }[lang]

    def _get_app(self):
        factory = AppFactory(build_version='2.40.0')
        app = factory.app
        app.langs = ['en', 'fra']

        module, form = factory.new_basic_module('register', 'case')
        form.source = self.get_xml('one_question_two_images').decode('utf-8')

        module.set_icon('en', self._get_menu_media('en'))
        module.set_icon('fra', self._get_menu_media('fra'))
        form.set_icon('en', self._get_menu_media('en'))

        return app

    def test_paths_download(self, validate_xform):
        app = self._get_app()
        module_name = app.modules[0].default_name()
        form_name = app.modules[0].forms[0].default_name()

        rows = download_multimedia_paths_rows(app)
        self.assertEqual(len(rows), 4)

        rows_by_path = {row[1][0]: row[1][2:] for row in rows}
        self.assertEqual(len(rows_by_path), 4)

        # English icon used twice: once in module, once in form
        path = self._get_menu_media('en')
        self.assertEqual(len(rows_by_path[path]), 2)
        self.assertTrue(rows_by_path[path][0].endswith(module_name))
        self.assertTrue(module_name in rows_by_path[path][1])
        self.assertTrue(form_name in rows_by_path[path][1])

        # French icon used just once, in module
        path = self._get_menu_media('fra')
        self.assertEqual(len(rows_by_path[path]), 1)
        self.assertTrue(rows_by_path[path][0].endswith(module_name))

        # Form question images each used once
        path = self._get_form_media('en')
        self.assertEqual(len(rows_by_path[path]), 1)
        self.assertTrue(rows_by_path[path][0].endswith(form_name))
        path = self._get_form_media('fra')
        self.assertEqual(len(rows_by_path[path]), 1)
        self.assertTrue(rows_by_path[path][0].endswith(form_name))

    def test_paths_validate(self, validate_xform):
        app = self._get_app()

        rows = (
            ('jr://nope.png', 'jr://yep.png'),                        # 0. error: existing path not in app
            (self._get_menu_media('en'), 'rose.png'),                 # 1. warning: unformatted path
            (self._get_menu_media('fra'), 'jr://lily.png'),           # 2. valid
            (self._get_form_media('en'), 'jr://file/tulip.jpg'),      # 3. valid
            (self._get_form_media('en'), 'jr://file/hyacinth.jpg'),   # 4. error & warning: dupe old and new paths
            (self._get_form_media('fra'), 'jr://file/hyacinth.jpg'),  # 5. warning: dupe new path
            (self._get_form_media('en'), self._get_form_media('en')), # 6. error: same old and new path
            (self._get_form_media('en'), 'jr://file/hyacinth.png'),   # 7. error & warning: dupe old path,
                                                                      #    changing file extension
        )
        (errors, warnings) = validate_multimedia_paths_rows(app, rows)

        self.assertEqual(len(errors), 4)
        self.assertTrue(re.search(r'0.*not.*found', errors[0]))
        self.assertTrue('already' in errors[1])
        self.assertTrue(self._get_form_media('en') in errors[1])
        self.assertTrue(re.search(r'6.*are both', errors[2]))
        self.assertTrue(self._get_form_media('en') in errors[2])
        self.assertTrue('already' in errors[3])

        self.assertEqual(len(warnings), 3)
        self.assertTrue(re.search(r'1.*replace', warnings[0]))
        self.assertTrue('already' in warnings[1])
        self.assertTrue('hyacinth' in warnings[1])
        self.assertTrue(re.search(r'7.*\bjpg\b.*\bpng\b', warnings[2]))

    @patch('dimagi.ext.couchdbkit.Document.get_db')
    def test_paths_upload(self, validate_xform, get_db):
        paths = {
            'jr://file/commcare/image/data/undefined-86sshg.jpg': 'jr://file/commcare/nin/ghosts.jpg',
            'jr://file/commcare/audio/module0_form0_en.mp3': 'jr://file/commcare/en/audio/laundry.mp3',
            'jr://file/commcare/image/data/la_la_la-zvj1k3.jpg': 'jr://file/commcare/nin/sin.jpg',
            'jr://file/commcare/audio/module0_en.mp3': 'jr://file/commcare/en/audio/dream.mp3',
            'jr://file/commcare/image/module1_case_list_menu_item_en.png': 'jr://file/commcare/image/lemonade.jpg',
            'jr://file/commcare/image/module0_form0_fra.jpg': 'jr://file/commcare/aff/pines.jpg',
            'jr://file/commcare/audio/module0_form0_fra.mp3': 'jr://file/commcare/fra/audio/souled.mp3',
            'jr://file/commcare/image/module0_form0_en.jpg': 'jr://file/commcare/aff/one_cell.jpg',
            'jr://file/commcare/image/module1_list_icon_name_1480.jpg': 'jr://file/commcare/image/le_monde.jpg',
            'jr://file/commcare/image/module0_en.jpg': 'jr://file/commcare/image/chime.jpg',
            'jr://file/commcare/image/module1_case_list_form_en.png': 'jr://file/commcare/image/trip.jpg',
            'jr://file/commcare/image/module1_case_list_lookup.jpg': 'jr://file/commcare/debut.jpg',
        }
        with open(os.path.join(os.path.dirname(__file__), 'data', 'manage-multimedia.json')) as f:
            source = json.load(f)
            app = Application.wrap(source)
            update_multimedia_paths(app, paths)

            self.assertEquals(len(app.all_media()), len(paths))

            # Module and form menu media
            self.assertEquals(
                app.modules[0].forms[0].icon_by_language('en'),
                'jr://file/commcare/aff/pines.jpg'
            )
            self.assertEquals(
                app.modules[0].forms[0].icon_by_language('fra'),
                'jr://file/commcare/aff/one_cell.jpg'
            )
            self.assertEquals(
                app.modules[0].icon_by_language('en'),
                'jr://file/commcare/image/chime.jpg'
            )
            self.assertEquals(
                app.modules[0].audio_by_language('en'),
                'jr://file/commcare/en/audio/dream.mp3'
            )
            self.assertEquals(
                app.modules[0].forms[0].audio_by_language('en'),
                'jr://file/commcare/fra/audio/souled.mp3'
            )
            self.assertEquals(
                app.modules[0].forms[0].audio_by_language('fra'),
                'jr://file/commcare/en/audio/laundry.mp3'
            )
            self.assertEquals(
                app.modules[0].forms[0].audio_by_language('en'),
                'jr://file/commcare/fra/audio/souled.mp3'
            )

            # Form media
            form_images = app.modules[1].forms[0].wrapped_xform().image_references()
            self.assertTrue('jr://file/commcare/nin/ghosts.jpg' in form_images)
            self.assertTrue('jr://file/commcare/nin/sin.jpg' in form_images)

            # Case list lookup
            self.assertEquals(
                app.modules[1].get_details()[0][1].lookup_image,
                'jr://file/commcare/debut.jpg'
            )

            # Case list icons
            self.assertEquals(
                app.modules[1].get_details()[0][1].columns[2].enum[0].value['en'],
                'jr://file/commcare/image/le_monde.jpg'
            )

            # Case list menu item
            self.assertEquals(
                app.modules[1].case_list.icon_by_language('en'),
                'jr://file/commcare/image/lemonade.jpg'
            )
            self.assertEquals(
                app.modules[1].case_list.icon_by_language('fra'),
                'jr://file/commcare/image/lemonade.jpg'
            )

            # Reg from cast list
            self.assertEquals(
                app.modules[1].case_list_form.icon_by_language('en'),
                'jr://file/commcare/image/trip.jpg'
            )
            self.assertEquals(
                app.modules[1].case_list_form.icon_by_language('fra'),
                'jr://file/commcare/image/trip.jpg'
            )
