from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.test import SimpleTestCase
import os

from mock import patch

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.hqmedia.view_helpers import download_multimedia_paths_rows


class ManagePathsTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def test_paths_download(self):
        factory = AppFactory(build_version='2.40.0')
        app = factory.app
        app.langs = ['en', 'fra']

        module, form = factory.new_basic_module('register', 'case')
        form.source = self.get_xml('one_question_two_images').decode('utf-8')
        module_name = module.default_name()
        form_name = form.default_name()

        menu_icon_path_en = 'jr://file/commcare/module0_en.png'
        menu_icon_path_fra = 'jr://file/commcare/module0_fra.png'
        form_question_path_en = 'jr://file/commcare/image/data/question1-fn3fu1.jpg'
        form_question_path_fra = 'jr://file/commcare/image/data/question1-1ppout.jpg'

        module.set_icon('en', menu_icon_path_en)
        module.set_icon('fra', menu_icon_path_fra)
        form.set_icon('en', menu_icon_path_en)

        rows = download_multimedia_paths_rows(app)
        self.assertEqual(len(rows), 4)

        rows_by_path = {row[1][0]: row[1][1:] for row in rows}
        self.assertEqual(len(rows_by_path), 4)

        # English icon used twice: once in module, once in form
        self.assertEqual(len(rows_by_path[menu_icon_path_en]), 2)
        self.assertTrue(rows_by_path[menu_icon_path_en][0].endswith(module_name))
        self.assertTrue(module_name in rows_by_path[menu_icon_path_en][1])
        self.assertTrue(form_name in rows_by_path[menu_icon_path_en][1])

        # French icon used just once, in module
        self.assertEqual(len(rows_by_path[menu_icon_path_fra]), 1)
        self.assertTrue(rows_by_path[menu_icon_path_fra][0].endswith(module_name))

        # Form question images each used once
        self.assertEqual(len(rows_by_path[form_question_path_en]), 1)
        self.assertTrue(rows_by_path[form_question_path_en][0].endswith(form_name))
        self.assertEqual(len(rows_by_path[form_question_path_fra]), 1)
        self.assertTrue(rows_by_path[form_question_path_fra][0].endswith(form_name))
