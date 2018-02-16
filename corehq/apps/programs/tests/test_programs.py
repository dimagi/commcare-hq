from __future__ import absolute_import
from django.test import SimpleTestCase
from corehq.apps.groups.tests.test_groups import WrapGroupTestMixin
from corehq.apps.programs.models import Program


class WrapProgramTest(WrapGroupTestMixin, SimpleTestCase):
    document_class = Program
