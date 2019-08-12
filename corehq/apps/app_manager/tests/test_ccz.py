# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import itertools
import os
import tempfile
import zipfile

from django.test import TestCase
from mock import patch

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.xform_builder import XFormBuilder
from corehq.apps.hqmedia.models import CommCareImage
from corehq.apps.hqmedia.tasks import check_ccz_multimedia_integrity, find_missing_locale_ids_in_ccz
from corehq.apps.hqmedia.views import iter_media_files
from corehq.util.test_utils import flag_enabled
from io import open


class CCZTest(TestCase):
    def setUp(self):
        self.domain = 'test-domain'
        self.factory = AppFactory(build_version='2.40.0', domain=self.domain)
        self.module, self.form = self.factory.new_basic_module('basic', 'patient')

        builder = XFormBuilder(self.form.name)
        builder.new_question(name='name', label='Name')
        self.form.source = builder.tostring(pretty_print=True).decode('utf-8')

        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images', 'favicon.png')
        with open(image_path, 'rb') as f:
            image_data = f.read()
            self.image = CommCareImage.get_by_data(image_data)
            self.image.attach_data(image_data, original_filename='icon.png')
            self.image.add_domain(self.domain)
            self.image.save()
            self.addCleanup(self.image.delete)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_missing_locale_ids(self, mock):
        files = self.factory.app.create_all_files()
        errors = find_missing_locale_ids_in_ccz(files)
        self.assertEqual(len(errors), 0)

        default_app_strings = files['default/app_strings.txt'].decode('utf-8').splitlines()
        files['default/app_strings.txt'] = "\n".join([line for line in default_app_strings
                                                      if not line.startswith("forms.m0f0")]).encode('utf-8')
        errors = find_missing_locale_ids_in_ccz(files)
        self.assertEqual(len(errors), 1)
        self.assertIn('forms.m0f0', errors[0])

    def test_multimedia_integrity(self):
        icon_path = 'jr://file/commcare/icon.png'
        self.module.set_icon('en', icon_path)
        self.factory.app.create_mapping(self.image, icon_path, save=False)

        zip_path = self._create_multimedia_integrity_zip(
            self.factory.app.create_media_suite(),
            list(self.factory.app.get_media_objects(remove_unused=True)))
        errors = check_ccz_multimedia_integrity(self.domain, zip_path)
        self.assertEqual(len(errors), 0)

        zip_path = self._create_multimedia_integrity_zip(self.factory.app.create_media_suite(), [])
        errors = check_ccz_multimedia_integrity(self.domain, zip_path)
        self.assertEqual(len(errors), 1)
        self.assertIn('commcare/icon.png', errors[0])

    def _create_multimedia_integrity_zip(self, media_suite, media_objects):
        # Creates a limited zip, containing only media suite and multimedia files
        files, errors = iter_media_files(media_objects)
        media_suite = self.factory.app.create_media_suite()
        files = itertools.chain(files, [('media_suite.xml', media_suite)])

        dummy, zip_path = tempfile.mkstemp()
        with open(zip_path, 'wb') as tmp:
            with zipfile.ZipFile(tmp, "w") as z:
                for path, data in files:
                    z.writestr(path, data, zipfile.ZIP_STORED)
        return zip_path
