from corehq.apps.groups.tests import WrapGroupTest
from corehq.apps.programs.models import Program


class WrapProgramTest(WrapGroupTest):
    document_class = Program
