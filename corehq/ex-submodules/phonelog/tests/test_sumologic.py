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

    def test_usererror(self):
        xform = self._get_xform('usererror_subreport')
        compiled_log = SumoLogicLog(self.domain, xform).compile()
        expected_log = (
            "[log_date=2018-02-22T17:21:21.201-05] [log_submission_date={received}] [log_type=error-config] "
            "[domain={domain}] [username=t1] [device_id=014915000230428] [app_version=260] "
            "[cc_version=2.43] [msg=This is a test user error] [app_id=73d5f08b9d55fe48602906a89672c214] "
            "[user_id=37cc2dcdb1abf5c16bab0763f435e6b7] [session=session] [expr=an expression]"
        ).format(domain=self.domain, received=self.received_on)

        self.assertEqual(expected_log, compiled_log)
