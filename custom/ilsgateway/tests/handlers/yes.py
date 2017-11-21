from __future__ import absolute_import
from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import YES_HELP
from custom.ilsgateway.tests.handlers.utils import ILSTestScript
import six


class TestYes(ILSTestScript):

    def test_yes(self):
        with localize('sw'):
            response = YES_HELP
        script = """
          5551234 > ndio
          5551234 < {0}
        """.format(six.text_type(response))
        self.run_script(script)
