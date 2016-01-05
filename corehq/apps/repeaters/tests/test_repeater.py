from StringIO import StringIO
from datetime import datetime, timedelta
from mock import MagicMock, patch

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.xml import V1

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.exceptions import DuplicateFormatException, IgnoreDocument
from corehq.apps.repeaters.models import (
    CaseRepeater,
    FormRepeater,
    RepeatRecord,
    RegisterGenerator)
from corehq.apps.repeaters.repeater_generators import BasePayloadGenerator
from couchforms.models import XFormInstance

case_id = "ABC123CASEID"
instance_id = "XKVB636DFYL38FNX3D38WV5EH"
update_instance_id = "ZYXKVB636DFYL38FNX3D38WV5"

case_block = """
<case>
    <case_id>%s</case_id>
    <date_modified>2011-12-19T00:00:00.000000Z</date_modified>
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
    <date_modified>2011-12-19T00:00:00.000000Z</date_modified>
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


class BaseRepeaterTest(TestCase):
    client = Client()

    @classmethod
    def post_xml(cls, xml, domain_name):
        f = StringIO(xml)
        f.name = 'form.xml'
        cls.client.post(
            reverse('receiver_post', args=[domain_name]), {
                'xml_submission_file': f
            }
        )

    @classmethod
    def repeat_records(cls, domain_name):
        return RepeatRecord.all(domain=domain_name, due_before=datetime.utcnow())


class RepeaterTest(BaseRepeaterTest):
    def setUp(self):

        self.domain = "test-domain"
        create_domain(self.domain)
        self.case_repeater = CaseRepeater(
            domain=self.domain,
            url='case-repeater-url',
            version=V1,
        )
        self.case_repeater.save()
        self.form_repeater = FormRepeater(
            domain=self.domain,
            url='form-repeater-url',
        )
        self.form_repeater.save()
        self.log = []
        self.post_xml(xform_xml, self.domain)

    def clear_log(self):
        for i in range(len(self.log)):
            self.log.pop()

    def make_post_fn(self, status_codes):
        status_codes = iter(status_codes)

        def post_fn(data, url, headers=None):
            status_code = status_codes.next()
            self.log.append((url, status_code, data, headers))

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
        #  this test should probably be divided into more units

        CommCareCase.get(case_id)

        def now():
            return datetime.utcnow()

        repeat_records = RepeatRecord.all(domain=self.domain, due_before=now())
        self.assertEqual(len(repeat_records), 2)

        self.clear_log()

        records_by_repeater_id = {}
        for repeat_record in repeat_records:
            repeat_record.fire(post_fn=self.make_post_fn([404, 404, 404]))
            repeat_record.save()
            records_by_repeater_id[repeat_record.repeater_id] = repeat_record

        for (url, status, data, headers) in self.log:
            self.assertEqual(status, 404)

        self.clear_log()

        next_check_time = now() + timedelta(minutes=60)

        repeat_records = RepeatRecord.all(
            domain=self.domain,
            due_before=now() + timedelta(minutes=15),
        )
        self.assertEqual(len(repeat_records), 0)

        repeat_records = RepeatRecord.all(
            domain=self.domain,
            due_before=next_check_time + timedelta(seconds=2),
        )
        self.assertEqual(len(repeat_records), 2)

        for repeat_record in repeat_records:
            self.assertLess(abs(next_check_time - repeat_record.next_check),
                            timedelta(seconds=3))
            repeat_record.fire(post_fn=self.make_post_fn([404, 200]))
            repeat_record.save()

        self.assertEqual(len(self.log), 4)

        # The following is pretty fickle and depends on which of
        #   - corehq.apps.repeaters.signals
        #   - casexml.apps.case.signals
        # gets loaded first.
        # This is deterministic but easily affected by minor code changes

        # check case stuff
        rec = records_by_repeater_id[self.case_repeater.get_id]
        self.assertEqual(self.log[1][:2], (self.case_repeater.get_url(rec), 200))
        self.assertIn('server-modified-on', self.log[1][3])
        check_xml_line_by_line(self, self.log[1][2], case_block)

        # check form stuff
        rec = records_by_repeater_id[self.form_repeater.get_id]
        self.assertEqual(self.log[3][:3],
                         (self.form_repeater.get_url(rec), 200, xform_xml))
        self.assertIn('received-on', self.log[3][3])

        repeat_records = RepeatRecord.all(
            domain=self.domain,
            due_before=next_check_time,
        )
        for repeat_record in repeat_records:
            self.assertEqual(repeat_record.succeeded, True)
            self.assertEqual(repeat_record.next_check, None)

        self.assertEqual(len(self.repeat_records(self.domain)), 0)

        self.post_xml(update_xform_xml, self.domain)
        self.assertEqual(len(self.repeat_records(self.domain)), 2)


class CaseRepeaterTest(BaseRepeaterTest, TestXmlMixin):
    @classmethod
    def setUpClass(cls):
        cls.domain_name = "test-domain"
        cls.domain = create_domain(cls.domain_name)
        cls.repeater = CaseRepeater(
            domain=cls.domain_name,
            url="case-repeater-url",
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.repeater.delete()

    def tearDown(self):
        try:
            # delete case, so that post of xform_xml creates new case as expected multiple-times
            CommCareCase.get(case_id).delete()
        except:
            pass
        for repeat_record in self.repeat_records(self.domain_name):
            repeat_record.delete()

    def test_case_close_format(self):
        # create a case
        self.post_xml(xform_xml, self.domain_name)
        payload = self.repeat_records(self.domain_name).all()[0].get_payload()
        self.assertXmlHasXpath(payload, '//*[local-name()="case"]')
        self.assertXmlHasXpath(payload, '//*[local-name()="create"]')

        # close the case
        CaseFactory().close_case(case_id)
        close_payload = self.repeat_records(self.domain_name).all()[1].get_payload()
        self.assertXmlHasXpath(close_payload, '//*[local-name()="case"]')
        self.assertXmlHasXpath(close_payload, '//*[local-name()="close"]')
        self.assertXmlHasXpath(close_payload, '//*[local-name()="update"]')

    def test_excluded_case_types_are_not_forwarded(self):
        self.repeater.exclude_case_types = ['repeater_case']
        self.repeater.save()
        # create a case
        self.post_xml(xform_xml, self.domain_name)
        # check no case forwarding happens
        self.assertEqual(0, len(self.repeat_records(self.domain_name).all()))


class RepeaterFailureTest(BaseRepeaterTest):

    def setUp(self):
        self.domain_name = "test-domain"
        self.domain = create_domain(self.domain_name)

        self.repeater = CaseRepeater(
            domain=self.domain_name,
            url='case-repeater-url',
            version=V1,
            format='other_format'
        )
        self.repeater.save()
        self.post_xml(xform_xml, self.domain)

    def tearDown(self):
        self.domain.delete()
        self.repeater.delete()
        repeat_records = RepeatRecord.all()
        for repeat_record in repeat_records:
            repeat_record.delete()

    def test_failure(self):
        payload = "some random case"

        @RegisterGenerator(CaseRepeater, 'other_format', 'XML')
        class NewCaseGenerator(BasePayloadGenerator):
            def get_payload(self, repeat_record, payload_doc):
                return payload

        repeat_record = self.repeater.register(CommCareCase.get(case_id))
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout', side_effect=Exception('Boom!')):
            repeat_record.fire()

        self.assertEquals(repeat_record.failure_reason, 'Boom!')
        self.assertFalse(repeat_record.succeeded)

        # Should be marked as successful after a successful run
        with patch('corehq.apps.repeaters.models.simple_post_with_cached_timeout'):
            repeat_record.fire()

        self.assertTrue(repeat_record.succeeded)


class IgnoreDocumentTest(BaseRepeaterTest):

    def setUp(self):
        self.domain = "test-domain"
        create_domain(self.domain)

        self.repeater = FormRepeater(
            domain=self.domain,
            url='form-repeater-url',
            version=V1,
            format='new_format'
        )
        self.repeater.save()

    def tearDown(self):
        self.repeater.delete()
        repeat_records = RepeatRecord.all()
        for repeat_record in repeat_records:
            repeat_record.delete()

    def test_ignore_document(self):
        """
        When get_payload raises IgnoreDocument, fire should call update_success
        """

        @RegisterGenerator(FormRepeater, 'new_format', 'XML')
        class NewFormGenerator(BasePayloadGenerator):
            def get_payload(self, repeat_record, payload_doc):
                raise IgnoreDocument

        repeat_records = RepeatRecord.all(
            domain=self.domain,
        )
        for repeat_record_ in repeat_records:
            repeat_record_.fire()

            self.assertIsNone(repeat_record_.next_check)
            self.assertTrue(repeat_record_.succeeded)


class TestRepeaterFormat(BaseRepeaterTest):
    def setUp(self):
        self.domain = "test-domain"
        create_domain(self.domain)
        self.post_xml(xform_xml, self.domain)

        self.repeater = CaseRepeater(
            domain=self.domain,
            url='case-repeater-url',
            version=V1,
            format='new_format'
        )
        self.repeater.save()

    def tearDown(self):
        self.repeater.delete()
        XFormInstance.get(instance_id).delete()
        repeat_records = RepeatRecord.all()
        for repeat_record in repeat_records:
            repeat_record.delete()

    def test_new_format_same_name(self):
        with self.assertRaises(DuplicateFormatException):
            @RegisterGenerator(CaseRepeater, 'case_xml', 'XML', is_default=False)
            class NewCaseGenerator(BasePayloadGenerator):
                def get_payload(self, repeat_record, payload_doc):
                    return "some random case"

    def test_new_format_second_default(self):
        with self.assertRaises(DuplicateFormatException):
            @RegisterGenerator(CaseRepeater, 'rubbish', 'XML', is_default=True)
            class NewCaseGenerator(BasePayloadGenerator):
                def get_payload(self, repeat_record, payload_doc):
                    return "some random case"

    def test_new_format_payload(self):
        payload = "some random case"

        @RegisterGenerator(CaseRepeater, 'new_format', 'XML')
        class NewCaseGenerator(BasePayloadGenerator):
            def get_payload(self, repeat_record, payload_doc):
                return payload

        repeat_record = self.repeater.register(CommCareCase.get(case_id))
        post_fn = MagicMock()
        repeat_record.fire(post_fn=post_fn)
        headers = self.repeater.get_headers(repeat_record)
        post_fn.assert_called_with(payload, self.repeater.url, headers=headers)


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
