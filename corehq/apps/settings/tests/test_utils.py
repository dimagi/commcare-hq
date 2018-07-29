from __future__ import absolute_import
from __future__ import unicode_literals
import os
from django.test import SimpleTestCase
from corehq.apps.settings.utils import get_temp_file


class GetTempFileTests(SimpleTestCase):

    def test_file_closed(self):
        """
        Check that an error is not raised if the file is closed by the caller
        """
        try:
            with get_temp_file() as (fd, name):
                os.close(fd)
        except Exception as err:
            self.fail('Failed with exception "{}"'.format(err))
        else:
            file_exists = os.access(name, os.F_OK)
            self.assertFalse(file_exists)

    def test_file_unused(self):
        """
        Check that an error is not raised if the file is unused by the caller
        """
        try:
            with get_temp_file() as (fd, name):
                pass
        except Exception as err:
            self.fail('Failed with exception "{}"'.format(err))
        else:
            file_exists = os.access(name, os.F_OK)
            self.assertFalse(file_exists)

    def test_file_deleted(self):
        """
        Check that an error is not raised if the file is deleted by the caller
        """
        try:
            with get_temp_file() as (fd, name):
                os.unlink(name)
        except Exception as err:
            self.fail('Failed with exception "{}"'.format(err))
