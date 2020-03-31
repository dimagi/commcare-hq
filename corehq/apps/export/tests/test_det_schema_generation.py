import os
import tempfile

from django.test import SimpleTestCase

from corehq.apps.export.det import generate_case_schema
from corehq.util.test_utils import TestFileMixin


class TestDETCaseSchema(SimpleTestCase, TestFileMixin):
    file_path = ['data', 'det']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = cls.get_json('case_schema')

    def test_generate_schema(self):
        # todo: all this tests is that the code successfully runs
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx') as tmp:
            generate_case_schema(self.schema, 'test', tmp)
