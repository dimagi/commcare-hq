# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import os
from django.test import SimpleTestCase

from corehq.apps.reports.util import validate_xform_for_edit
from corehq.apps.reports.exceptions import EditFormValidationError
from corehq.apps.app_manager.xform import XForm
from corehq.util.test_utils import TestFileMixin

DOMAIN = 'test_domain'


class TestValidateXFormForEdit(SimpleTestCase, TestFileMixin):
    file_path = ('edit_forms',)
    root = os.path.dirname(__file__)

    def test_bad_calculate(self):
        source = self.get_xml('bad_calculate')
        xform = XForm(source)
        with self.assertRaises(EditFormValidationError):
            validate_xform_for_edit(xform)
