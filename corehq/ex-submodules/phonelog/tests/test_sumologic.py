from __future__ import absolute_import

from __future__ import unicode_literals
import os
from datetime import datetime

from django.test import SimpleTestCase

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
        compiled_log = SumoLogicLog(self.domain, xform).log_subreport()
        expected_log = (
            "[log_date=2018-02-13T15:19:30.622-05] [log_submission_date={received}] [log_type=maintenance] "
            "[domain={domain}] [username=t1] [device_id=014915000230428] [app_version=260] "
            "[cc_version=2.43] [msg=Succesfully submitted 1 device reports to server.]"
        ).format(domain=self.domain, received=self.received_on)

        self.assertEqual(expected_log, compiled_log)

    def test_usererror(self):
        xform = self._get_xform('usererror_subreport')
        compiled_log = SumoLogicLog(self.domain, xform).user_error_subreport()
        expected_log = (
            "[log_date=2018-02-22T17:21:21.201-05] [log_submission_date={received}] [log_type=error-config] "
            "[domain={domain}] [username=t1] [device_id=014915000230428] [app_version=260] "
            "[cc_version=2.43] [msg=This is a test user error] [app_id=73d5f08b9d55fe48602906a89672c214] "
            "[user_id=37cc2dcdb1abf5c16bab0763f435e6b7] [session=session] [expr=an expression]"
        ).format(domain=self.domain, received=self.received_on)

        self.assertEqual(expected_log, compiled_log)

    def test_forceclose(self):
        xform = self._get_xform('forceclose_subreport')
        compiled_log = SumoLogicLog(self.domain, xform).force_close_subreport()
        expected_log = (
            "[log_date=2018-02-22T17:21:21.232-05] [log_submission_date={received}] [log_type=forceclose] "
            "[domain={domain}] [username=t1] [device_id=014915000230428] [app_version=260] "
            "[cc_version=2.43] "
            """[msg=java.lang.RuntimeException: Unable to start activity ComponentInfo{{org.commcare.dalvik.debug/org.commcare.activities.MenuActivity}}: java.lang.RuntimeException
        at android.app.ActivityThread.performLaunchActivity(ActivityThread.java:2416)
        at android.app.ActivityThread.handleLaunchActivity(ActivityThread.java:2476)
        at android.app.ActivityThread.-wrap11(ActivityThread.java)
        at android.app.ActivityThread$H.handleMessage(ActivityThread.java:1344)
        at android.os.Handler.dispatchMessage(Handler.java:102)
        at android.os.Looper.loop(Looper.java:148)
        at android.app.ActivityThread.main(ActivityThread.java:5417)
        at java.lang.reflect.Method.invoke(Native Method)
        at com.android.internal.os.ZygoteInit$MethodAndArgsCaller.run(ZygoteInit.java:726)
        at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:616)
      Caused by: java.lang.RuntimeException
        at org.commcare.activities.MenuActivity.onCreateSessionSafe(MenuActivity.java:35)
        at org.commcare.activities.SessionAwareHelper.onCreateHelper(SessionAwareHelper.java:21)
        at org.commcare.activities.SessionAwareCommCareActivity.onCreate(SessionAwareCommCareActivity.java:20)
        at android.app.Activity.performCreate(Activity.java:6251)
        at android.app.Instrumentation.callActivityOnCreate(Instrumentation.java:1107)
        at android.app.ActivityThread.performLaunchActivity(ActivityThread.java:2369)
        ... 9 more] [app_id=73d5f08b9d55fe48602906a89672c214] """
            "[user_id=37cc2dcdb1abf5c16bab0763f435e6b7] [session=readable_session] [device_model=Nexus 7]"
        ).format(domain=self.domain, received=self.received_on)
        self.assertEqual(expected_log, compiled_log)
