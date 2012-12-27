from StringIO import StringIO
from datetime import datetime, timedelta
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.xml import V1
from corehq.apps.receiverwrapper.models import RepeatRecord, CaseRepeater, FormRepeater
from couchforms.models import XFormInstance
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

case_id = "ABC123CASEID"
instance_id = "XKVB636DFYL38FNX3D38WV5EH"
update_instance_id = "ZYXKVB636DFYL38FNX3D38WV5"

case_block = """
<case>
    <case_id>%s</case_id>
    <date_modified>2011-12-19</date_modified>
    <create>
        <case_type_id>repeater_case</case_type_id>
        <user_id>O2XLT0WZW97W1A91E2W1Y0NJG</user_id>
        <case_name>ABC 123</case_name>
        <external_id>ABC 123</external_id>
    </create>
</case>
""" % case_id

update_block = """
<case>
    <case_id>%s</case_id>
    <date_modified>2011-12-19</date_modified>
    <update>
        <case_name>ABC 234</case_name>
    </update>
</case>
""" % case_id


xform_xml_template = """<?xml version='1.0' ?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="https://www.commcarehq.org/test/repeater/">
	<woman_name>Alpha</woman_name>
	<husband_name>Beta</husband_name>
	<meta>
		<deviceID>O2XLT0WZW97W1A91E2W1Y0NJG</deviceID>
		<timeStart>2011-10-01T15:25:18.404-04</timeStart>
		<timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
		<username>admin</username>
		<userID>O2XLT0WZW97W1A91E2W1Y0NJG</userID>
		<instanceID>%s</instanceID>
	</meta>
%s
</data>
"""
xform_xml = xform_xml_template % (instance_id, case_block)
update_xform_xml = xform_xml_template % (update_instance_id, update_block)

class RepeaterTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.domain = "test-domain"
        self.case_repeater = CaseRepeater(domain=self.domain, url='case-repeater-url', version=V1)
        self.case_repeater.save()
        self.form_repeater = FormRepeater(domain=self.domain, url='form-repeater-url')
        self.form_repeater.save()
        self.log = []
        self.post_xml(xform_xml)

    def post_xml(self, xml):
        f = StringIO(xml)
        f.name = 'form.xml'
        self.client.post(
            reverse('receiver_post', args=[self.domain]), {
                'xml_submission_file': f
            }
        )

    def clear_log(self):
        for i in range(len(self.log)): self.log.pop()

    def make_post_fn(self, status_codes):
        status_codes = iter(status_codes)
        def post_fn(data, url):
            status_code = status_codes.next()
            self.log.append((url, status_code, data))
            class resp:
                status = status_code
            return resp
        return post_fn
    def tearDown(self):
        self.case_repeater.delete()
        self.form_repeater.delete()
        XFormInstance.get(instance_id).delete()
        repeat_records = RepeatRecord.all()
        for repeat_record in repeat_records:
            repeat_record.delete()


    def test_repeater(self):

        CommCareCase.get(case_id)

        now = datetime.utcnow()


        repeat_records = RepeatRecord.all(domain=self.domain, due_before=now)
        self.assertEqual(len(repeat_records), 2)

        self.clear_log()


        for repeat_record in repeat_records:
            repeat_record.fire(post_fn=self.make_post_fn([404, 404, 404]))
            repeat_record.save()

        for (url, status, data) in self.log:
            self.assertEqual(status, 404)

        self.clear_log()

        in30min = now + timedelta(minutes=30)

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=now + timedelta(minutes=15))
        self.assertEqual(len(repeat_records), 0)

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=in30min + timedelta(seconds=1))
        self.assertEqual(len(repeat_records), 2)

        for repeat_record in repeat_records:
            self.assertLess(abs(in30min - repeat_record.next_check), timedelta(seconds=1))
            repeat_record.fire(post_fn=self.make_post_fn([404, 200]))
            repeat_record.save()

        self.assertEqual(len(self.log), 4)
        self.assertEqual(self.log[1], (self.form_repeater.url, 200, xform_xml))
        self.assertEqual(self.log[3][:2], (self.case_repeater.url, 200))
        check_xml_line_by_line(self, self.log[3][2], case_block)

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=in30min)
        for repeat_record in repeat_records:
            self.assertEqual(repeat_record.succeeded, True)
            self.assertEqual(repeat_record.next_check, None)


        repeat_records = RepeatRecord.all(domain=self.domain, due_before=now)
        self.assertEqual(len(repeat_records), 0)

        self.post_xml(update_xform_xml)

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=now)
        self.assertEqual(len(repeat_records), 2)


class RepeaterLockTest(TestCase):

    def testLocks(self):
        r = RepeatRecord(domain='test')
        r.save()
        r2 = RepeatRecord.get(r._id)
        self.assertTrue(r.acquire_lock(datetime.utcnow()))
        r3 = RepeatRecord.get(r._id)
        self.assertFalse(r2.acquire_lock(datetime.utcnow()))
        self.assertFalse(r3.acquire_lock(datetime.utcnow()))
        r.release_lock()
        r4 = RepeatRecord.get(r._id)
        self.assertTrue(r4.acquire_lock(datetime.utcnow()))
        