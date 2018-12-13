from __future__ import absolute_import
from __future__ import unicode_literals
import json
from django.test import SimpleTestCase
import os

from mock import patch

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory
from io import open


class MediaTest(SimpleTestCase):

    def test_paths_download(self):
        self.assertEqual(3, 4)
        pass

