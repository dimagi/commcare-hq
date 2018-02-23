from __future__ import absolute_import

import os
from datetime import datetime

from django.test import SimpleTestCase

from dimagi.utils.parsing import string_to_utc_datetime
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.utils import convert_xform_to_json
from phonelog.utils import SumoLogicLog


class TestSumologic(SimpleTestCase, TestXmlMixin):
    root = os.path.dirname(__file__)
    file_path = ('data',)

    def setUp(self):
        self.domain = 'test_domain'
        self.received_on = datetime.utcnow()

    def _get_xform(self, filename):
        xform = FormProcessorInterface(self.domain).new_xform(convert_xform_to_json(self.get_xml(filename)))
        xform.received_on = self.received_on
        return xform

    def test_log_error(self):
        xform = self._get_xform('log_subreport')
        compiled_log = SumoLogicLog(self.domain, xform).compile()
        expected_log = (
            "[log_date=2018-02-13T15:19:30.622-05] [log_submission_date={received}] [log_type=maintenance] "
            "[domain={domain}] [username=t1] [device_id=014915000230428] [app_version=260] "
            "[cc_version=2.43] [msg=Succesfully submitted 1 device reports to server.]"
        ).format(domain=self.domain, received=self.received_on)

        self.assertEqual(expected_log, compiled_log)
