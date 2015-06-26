from django.test import SimpleTestCase
from corehq.apps.groups.tests import WrapGroupTestMixin
from corehq.apps.programs.models import Program


class WrapProgramTest(WrapGroupTestMixin, SimpleTestCase):
    document_class = Program
