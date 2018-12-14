from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

import re

from mock import patch

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.hqmedia.view_helpers import download_multimedia_paths_rows, validate_multimedia_paths_rows


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

    def test_paths_download(self, mock):
        app = self._get_app()
        module_name = app.modules[0].default_name()
        form_name = app.modules[0].forms[0].default_name()

        rows = download_multimedia_paths_rows(app)
        self.assertEqual(len(rows), 4)

        rows_by_path = {row[1][0]: row[1][1:] for row in rows}
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

    def test_paths_validate(self, mock):
        app = self._get_app()

        rows = (
            (self._get_menu_media('en'),),                            # 1. error: too few columns
            ('jr://nope.png', 'jr://yep.png'),                        # 2. error: existing path not in app
            (self._get_menu_media('en'), 'rose.png'),                 # 3. warning: unformatted path
            (self._get_menu_media('fra'), 'jr://lily.png'),           # 4. valid
            (self._get_form_media('en'), 'jr://file/tulip.png'),      # 5. valid
            (self._get_form_media('en'), 'jr://file/hyacinth.png'),   # 6. error & warning: dupe old and new paths
            (self._get_form_media('fra'), 'jr://file/hyacinth.png'),  # 7. warning: dupe new path
        )
        (valid, errors, warnings) = validate_multimedia_paths_rows(app, rows)

        self.assertEqual(valid, 4)

        self.assertEqual(len(errors), 3)
        self.assertTrue(re.search(r'1.*columns', errors[0]))
        self.assertTrue(re.search(r'2.*not.*found', errors[1]))
        self.assertTrue('already' in errors[2])
        self.assertTrue(self._get_form_media('en') in errors[2])

        self.assertEqual(len(warnings), 2)
        self.assertTrue(re.search(r'3.*replace', warnings[0]))
        self.assertTrue('already' in warnings[1])
        self.assertTrue('hyacinth' in warnings[1])
